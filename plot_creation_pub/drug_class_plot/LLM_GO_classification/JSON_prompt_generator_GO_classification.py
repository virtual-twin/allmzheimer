import os
import sys
import json
import logging
from neo4j import GraphDatabase
from dotenv import load_dotenv
import tiktoken

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from src_pub.utils.logging_config import setup_logging

# Load environment variables from .env file
load_dotenv()

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# intro
intro = """
	You are a language model that classifies medical drugs based on the Gene Ontology (GO) process the drug mainly works on.
	You will be provided with the name of the drug, a reason describing what biological process is mainly important for its selection for repurposing and a general list of GO processes the drug works on.
    However, the repurposing of the drug is not important to you but the main important Gene Ontology Process it works on is.
	Based on the data available, you have to provide the most important Gene Ontology term the drug works on.
    You have to provide it EXACTLY as it is given in the list of GO terms at the end of the prompt.
	It is mandatory,  that you choose only one of the GO terms for the drug, spell it exactly as provided and provide the classification in a valid JSON format like this: 
        
        "{\n"
        '   "Drug_Classification": "your classification here"\n'
        "}"
        Do only provide this particular valid json format at any cost and follow the naming of the classifications provided strictly.
        """

# outro
outro = """
	It is mandatory,  that you choose only one of the GO terms (as provided in the list but selected based on the reason) for the drug and provide the exactly spelled GO term in a valid JSON format like this: 
	This is the mandatory form for your JSON output:
	"{\n"
  	'   "Drug_Classification": "Mainly important GO-term exactly spelled here"\n'
	"}"
	Do only provide this particular valid json format at any cost and follow the naming of the classifications provided strictly.
        """


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

def generate_prompt(drug_info):
    prompt = intro
    prompt += f"{json.dumps(drug_info, indent=2, ensure_ascii=False)}\n\n"
    prompt += outro
    return prompt

def get_drug_info(uri, user, password, drugbank_id, skipped_counter):
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info("Database connection established successfully.")

        with driver.session() as session:
            logger.info(f"Retrieving information for Drug node with drugbankId: {drugbank_id}")

            result = session.run("""
                MATCH (d:Drug {drugbankId: $drugbank_id})
                RETURN 
                    d.name AS name,
                    d.reason_rating_0 AS reason_rating_0,
                    d.affectedGoProcess AS affectedGoProcess
            """, drugbank_id=drugbank_id)
            
            drug_info = None
            for record in result:
                if drug_info is None:
                    drug_info = {
                        'name': record['name'],
                        'reason_rating_0': record['reason_rating_0'],
                        'affectedGoProcess': record['affectedGoProcess'],
                        'drugbankId': drugbank_id  # Add drugbankId to the drug_info
                    }

            if drug_info:
                logger.info(f"Drug node properties: {drug_info}")
            else:
                logger.warning(f"No Drug node found with drugbankId: {drugbank_id}")
                return skipped_counter

            # Generate prompt using the generate_prompt function
            prompt = generate_prompt(drug_info)
            logger.info(f"Prompt generated in get_drug_info: {prompt}")

          

            # Save the prompt to a JSON file
            filename = f"{drugbank_id}.json"
            output_dir = # Provide output directory here
            os.makedirs(output_dir, exist_ok=True)
            file_path = os.path.join(output_dir, filename)
            with open(file_path, 'w') as json_file:
                json.dump({"drugbankId": drugbank_id, "name": drug_info.get('name', 'Unknown'), "prompt": prompt}, json_file, indent=4)
            logger.info(f"Prompt saved to {file_path}")

            return {
                "drug_name": drug_info.get("name", "Unknown"),
                "prompt": prompt,
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
    skipped_counter = get_drug_info(uri, user, password, drug_id, skipped_counter)

logger.info(f"Total skipped nodes: {skipped_counter}")

