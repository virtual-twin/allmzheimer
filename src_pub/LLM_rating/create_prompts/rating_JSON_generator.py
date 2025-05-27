# Based upon 'directionality_JSON_prompt_generator'

import os
import sys
import json
import logging
from neo4j import GraphDatabase
from dotenv import load_dotenv
import tiktoken

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from utils.logging_config import setup_logging

# Load environment variables from .env file
load_dotenv()

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

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

def calculate_token_length(prompt):
    tokenizer = tiktoken.get_encoding("cl100k_base")
    tokens = tokenizer.encode(prompt)
    return len(tokens)

def get_all_drugs(uri, user, password):
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info("Database connection established successfully.")

        with driver.session() as session:
            result = session.run("MATCH (d:Drug) RETURN d.drugbankId AS drugbank_id")
            drug_ids = [record['drugbank_id'] for record in result]
            return drug_ids

    except Exception as e:
        logger.critical(f"Failed to establish database connection or retrieve drug IDs: {str(e)}")
        return []
    finally:
        if 'driver' in locals():
            driver.close()

def generate_prompt(drug_info, neighbors_info):
    prompt = intro
    prompt += f"{json.dumps(drug_info, indent=2, ensure_ascii=False)}\n\n"
    
    prompt += "These biological processes are associated with the drug and the Alzheimer's pathology:\n"
    for neighbor in neighbors_info:
        prompt += f"Node properties: {json.dumps(neighbor['node'], indent=2, ensure_ascii=False)}\n\n"
     
    # Append the mandatory form to the prompt
    prompt += MANDATORY_FORM
        
    return prompt

def get_drug_and_neighbors_info(uri, user, password, drugbank_id, skipped_counter):
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info("Database connection established successfully.")

        with driver.session() as session:
            logger.info(f"Retrieving information for Drug node with drugbankId: {drugbank_id}")

            # Retrieve drug node and its neighbors with specified properties
            result = session.run("""
                MATCH (d:Drug {drugbankId: $drugbank_id})
                OPTIONAL MATCH (d)-[r]->(b:BiologicalProcess)
                RETURN 
                    d.pharmacodynamics AS pharmacodynamics,
                    d.description AS description,
                    d.clinicalDescription AS clinicalDescription,
                    d.mechanismOfAction AS mechanismOfAction,
                    d.affectedGoProcess AS affectedGoProcess,
                    d.name AS name,
                    b.label AS label,
                    r
            """, drugbank_id=drugbank_id)
            
            drug_info = None
            neighbors_info = []
            for record in result:
                if drug_info is None:
                    drug_info = {
                        'pharmacodynamics': record['pharmacodynamics'],
                        'description': record['description'],
                        'clinicalDescription': record['clinicalDescription'],
                        'mechanismOfAction': record['mechanismOfAction'],
                        'affectedGoProcess': record['affectedGoProcess'],
                        'name': record['name'],
                        'drugbankId': drugbank_id  # Add drugbankId to the drug_info
                    }

                if record['label']:
                    neighbor_info = {
                        'node': {'label': record['label']},
                    }
                    neighbors_info.append(neighbor_info)

            if drug_info:
                logger.info(f"Drug node properties: {drug_info}")
            else:
                logger.warning(f"No Drug node found with drugbankId: {drugbank_id}")
                return skipped_counter

            if neighbors_info:
                logger.info(f"Found {len(neighbors_info)} neighbor nodes.")
                for neighbor in neighbors_info:
                    logger.debug(f"Node properties: {neighbor['node']}")
            else:
                logger.warning(f"No neighbor nodes found for Drug node with drugbankId: {drugbank_id}")

            # Generate prompt using the updated generate_prompt function
            prompt = generate_prompt(drug_info, neighbors_info)
            logger.info(f"Prompt generated in get_drug_and_neighbors_info: {prompt}")

            # Calculate token length
            token_length = calculate_token_length(prompt)
            if token_length > 8000:
                logger.warning(f"Token length exceeded 8000. Actual token length: {token_length}")
            else:
                logger.info(f"Token length of the prompt - Lower than 8000: {token_length}")

            # Save the prompt to a JSON file
            filename = f"{drugbank_id}.json"
            output_dir = "directionality_prompts"
            os.makedirs(output_dir, exist_ok=True)
            file_path = os.path.join(output_dir, filename)
            with open(file_path, 'w') as json_file:
                json.dump({"drugbankId": drugbank_id, "name": drug_info.get('name', 'Unknown'), "prompt": prompt}, json_file, indent=4)
            logger.info(f"Prompt saved to {file_path}")

            return {
                "drug_name": drug_info.get("name", "Unknown"),
                "prompt": prompt,
                "token_length": token_length
            }

    except Exception as e:
        logger.critical(f"Failed to establish database connection or retrieve information: {str(e)}")
    finally:
        if 'driver' in locals():
            driver.close()
    return skipped_counter

# Connection details
uri = os.getenv("uri")
user = os.getenv("username")
password = os.getenv("password")

# Get all drug IDs
logger.warning("Initializing script to retrieve all Drug nodes.")
drug_ids = get_all_drugs(uri, user, password)

# Process each drug
skipped_counter = 0
for drug_id in drug_ids:
    skipped_counter = get_drug_and_neighbors_info(uri, user, password, drug_id, skipped_counter)

logger.info(f"Total skipped nodes: {skipped_counter}")
