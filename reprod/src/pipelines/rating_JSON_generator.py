# file: src/pipelines/generate_directionality_prompts.py
# Based upon 'directionality_JSON_prompt_generator'

import os
import sys
import json
import logging
from typing import List, Tuple, Dict, Optional

from neo4j import GraphDatabase
from dotenv import load_dotenv
import tiktoken

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.logging_config import setup_logging

# --- Configuration -----------------------------------------------------------
# Destination directory for prompt JSONs (bind-mount this for users)
PROMPTS_DIR = os.getenv("PROMPTS_DIR", "/app/exports/prompts")

# Strings preserved exactly to keep identical prompt text
MANDATORY_FORM = """
        Remember, only about 0.01 percent of the drugs you assess will be selected for further testing for Alzheimer's disease drug repurposing.
        You have to base your reason on the information you have on the drug and the biological processes it impacts.
        This is the mandatory form for your JSON output:
        
        "{\n"
        '   "reason_rating": "your reason here"\n'
        '   "rating": number from 0 to 1,\n'  
        "}"
        Do only provide this particular valid json format at any cost.
        
        """

intro = """ 
        You are a careful pharmaceutical scientist responsible for selecting drugs to repurpose for Alzheimer's disease.
        You have strictly limited resources and can only select the most promising drugs.
        You need to rate the drug on a scale from 0 to 1 to classify how promising you consider the repurposing of the drug to be based on careful assessment.
        The higher the number (1 at max), the more promising you will consider the drug.
        You will receive information on a drug that have an impact on biological processes. These biological processes have an association with Alzheimer's. 
        You have to decide - based on the information you receive concerning the drug - what impact the drug has on the biological processes given along.
        You also have to consider if the biological processes impacted by the drug are sufficiently specific to be impacted by a drug. 
        Your resources are highly limited, so you can only provide high ratings to drugs that are very likely to succeed in treating Alzheimer's.
        Also you have to base your reason on the information you have on the drug and the biological processes it impacts.       
            
        Be very careful with what you consider to be promising since this has a direct impact on patients.

        Let your assessment be guided by these questions:
        1. Are the biological processes the drug targets relevant for driving Alzheimer's?
        2. Does the directionality of the impact of the drug on the biological processes - based on the information you have on the drug - have a preventing or curing effect on Alzheimer's?  
        3. Is it highly likely that the drug can be taken by patients to prevent or treat Alzheimer's?

        Provide your reasoning in 'reason_rating' in your JSON output.

        This is the mandatory form for your JSON output:
        "{\n"
        '   "reason_rating": "your reason here"\n'
        '   "rating": number from 0 to 1,\n'  
        "}"

        Follow these instructions and always provide your response as JSON in this format.
        """

# --- Runtime setup -----------------------------------------------------------

def _resolve_creds() -> Tuple[str, str, str]:
    load_dotenv()
    uri = os.getenv("uri", "bolt://neo4j:7687")
    user = os.getenv("username", "neo4j")
    pwd = os.getenv("password")
    neo_auth = os.getenv("NEO4J_AUTH", "")
    if not pwd and neo_auth.startswith("neo4j/"):
        pwd = neo_auth[len("neo4j/"):]
    if not pwd:
        raise RuntimeError("Neo4j password not provided via 'password' or NEO4J_AUTH.")
    return uri, user, pwd

def calculate_token_length(prompt: str) -> int:
    tokenizer = tiktoken.get_encoding("cl100k_base")
    tokens = tokenizer.encode(prompt)
    return len(tokens)

def _ensure_output_dir() -> str:
    os.makedirs(PROMPTS_DIR, exist_ok=True)
    return PROMPTS_DIR

# --- Core logic --------------------------------------------------------------

def get_all_drugs(uri: str, user: str, password: str) -> List[str]:
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        logging.debug("Database connection established successfully.")
        with driver.session() as session:
            result = session.run("MATCH (d:Drug) RETURN d.drugbankId AS drugbank_id ORDER BY d.drugbankId ASC")
            drug_ids = [record["drugbank_id"] for record in result if record["drugbank_id"]]
            return drug_ids
    except Exception as e:
        logging.error(f"Failed to establish database connection or retrieve drug IDs: {str(e)}")
        return []
    finally:
        if "driver" in locals():
            driver.close()

def generate_prompt(drug_info: Dict[str, object], neighbors_info: List[Dict[str, Dict[str, str]]]) -> str:
    # Preserve exact composition and whitespace
    prompt = intro
    prompt += f"{json.dumps(drug_info, indent=2, ensure_ascii=False)}\n\n"
    prompt += "These biological processes are associated with the drug and the Alzheimer's pathology:\n"
    for neighbor in neighbors_info:
        prompt += f"Node properties: {json.dumps(neighbor['node'], indent=2, ensure_ascii=False)}\n\n"
    prompt += MANDATORY_FORM
    return prompt

def get_drug_and_neighbors_info(
    uri: str,
    user: str,
    password: str,
    drugbank_id: str,
    skipped_counter: int
):
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        logging.debug("Database connection established successfully.")

        with driver.session() as session:
            logging.debug(f"Retrieving information for Drug node with drugbankId: {drugbank_id}")

            # ORDER BY ensures deterministic neighbor listing
            result = session.run(
                """
                MATCH (d:Drug {drugbankId: $drugbank_id})
                OPTIONAL MATCH (d)-[r]->(b:BiologicalProcess)
                WITH d, b, r
                ORDER BY b.label ASC
                RETURN 
                    d.pharmacodynamics AS pharmacodynamics,
                    d.description AS description,
                    d.clinicalDescription AS clinicalDescription,
                    d.mechanismOfAction AS mechanismOfAction,
                    d.affectedGoProcess AS affectedGoProcess,
                    d.name AS name,
                    b.label AS label,
                    r
                """,
                drugbank_id=drugbank_id,
            )

            drug_info: Optional[Dict[str, object]] = None
            neighbors_info: List[Dict[str, Dict[str, str]]] = []

            for record in result:
                if drug_info is None:
                    drug_info = {
                        "pharmacodynamics": record["pharmacodynamics"],
                        "description": record["description"],
                        "clinicalDescription": record["clinicalDescription"],
                        "mechanismOfAction": record["mechanismOfAction"],
                        "affectedGoProcess": record["affectedGoProcess"],
                        "name": record["name"],
                        "drugbankId": drugbank_id,
                    }
                if record["label"]:
                    neighbors_info.append({"node": {"label": record["label"]}})

            if drug_info:
                logging.debug(f"Drug node properties: {drug_info}")
            else:
                logging.warning(f"No Drug node found with drugbankId: {drugbank_id}")
                return skipped_counter

            if neighbors_info:
                logging.debug(f"Found {len(neighbors_info)} neighbor nodes.")
            else:
                logging.warning(f"No neighbor nodes found for Drug node with drugbankId: {drugbank_id}")

            prompt = generate_prompt(drug_info, neighbors_info)
            logging.debug(f"Prompt generated in get_drug_and_neighbors_info for drug {drugbank_id}")

            token_length = calculate_token_length(prompt)
            if token_length > 8000:
                logging.warning(f"Token length exceeded 8000. Actual token length: {token_length}")
            else:
                logging.debug(f"Token length of the prompt - Lower than 8000: {token_length}")

            # Save JSON, preserving filename pattern
            out_dir = _ensure_output_dir()
            filename = f"{drugbank_id}.json"
            file_path = os.path.join(out_dir, filename)
            with open(file_path, "w", encoding="utf-8") as json_file:
                json.dump(
                    {"drugbankId": drugbank_id, "name": drug_info.get("name", "Unknown"), "prompt": prompt},
                    json_file,
                    indent=4,
                    ensure_ascii=False,
                )
            logging.debug(f"Prompt saved to {file_path}")

            return {
                "drug_name": drug_info.get("name", "Unknown"),
                "prompt": prompt,
                "token_length": token_length,
            }

    except Exception as e:
        logging.critical(f"Failed to establish database connection or retrieve information: {str(e)}")
    finally:
        if "driver" in locals():
            driver.close()
    return skipped_counter

def main() -> int:
    setup_logging()
    logging.warning("Initializing script to retrieve all Drug nodes.")
    uri, user, password = _resolve_creds()

    # Ensure output directory exists (bind mount recommended)
    _ensure_output_dir()

    drug_ids = get_all_drugs(uri, user, password)
    skipped_counter = 0
    for drug_id in drug_ids:
        skipped_counter = get_drug_and_neighbors_info(uri, user, password, drug_id, skipped_counter)

    logging.info(f"Total skipped nodes: {skipped_counter}")
    return 0

if __name__ == "__main__":
    sys.exit(main())