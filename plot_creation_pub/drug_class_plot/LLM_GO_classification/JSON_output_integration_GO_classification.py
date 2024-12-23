import os
import sys
import json
import logging
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from src_pub.utils.logging_config import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

def update_drug_node(session, drugbank_id, classification, token_length, index):
    try:
        # Create property name with suffix based on directory index
        classification_property = f"USP_classification_{index}" # Property name needs renaming since approach is now based on GO term

        session.run(f"""
            MATCH (d:Drug {{drugbankId: $drugbank_id}})
            SET d.{classification_property} = $classification
            RETURN d
        """, drugbank_id=drugbank_id, classification=classification)

        # Verify the update
        result = session.run(f"""
            MATCH (d:Drug {{drugbankId: $drugbank_id}})
            RETURN d.{classification_property} AS classification
        """, drugbank_id=drugbank_id)

        record = result.single()
        if record:
            logger.info(f"Updated Drug node with drugbankId: {drugbank_id}")
            logger.info(f"{classification_property}: {record['classification']}")
        else:
            logger.error(f"Failed to update Drug node with drugbankId: {drugbank_id}")

    except Exception as e:
        logger.error(f"An error occurred while updating the drug node: {str(e)}")

def process_json_files(directories, uri, user, password):
    failed_updates = 0
    total_files = 0
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info("Database connection established successfully.")

        for index, directory in enumerate(directories):
            json_files = [f for f in os.listdir(directory) if f.endswith('.json')]
            total_files += len(json_files)
            for json_file in json_files:
                try:
                    file_path = os.path.join(directory, json_file)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        response_data = f.read()

                    logger.debug(f"Raw response_data: {response_data}")
                    logger.debug(f"response_data type before json.loads: {type(response_data)}")

                    # Clean and ensure the JSON data integrity
                    response_data = response_data.strip()
                    logger.debug(f"Cleaned response_data: {response_data}")

                    try:
                        response_json = json.loads(response_data)
                        logger.debug(f"response_json type after json.loads: {type(response_json)}")
                        logger.debug(f"response_json content after json.loads: {response_json}")
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON decode error in file {file_path}: {str(e)}")
                        failed_updates += 1
                        continue

                    # Extract the "Drug_Classification" from the response
                    classification_json = response_json.get("response", "")
                    try:
                        classification_dict = json.loads(classification_json)
                        classification = classification_dict.get("Drug_Classification", "")
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON decode error for classification in file {file_path}: {str(e)}")
                        failed_updates += 1
                        continue

                    if not classification:
                        logger.error(f"No classification found in file {file_path}")
                        failed_updates += 1
                        continue

                    # Extract drugbank_id from filename and handle special characters
                    drugbank_id = json_file.split('_')[-1].replace('.json', '')
                    
                    # Call update_drug_node for each JSON file
                    with driver.session() as session:
                        # Calculate token length (assuming response_data is the prompt for token length)
                        token_length = len(response_data)
                        update_drug_node(session, drugbank_id, classification, token_length, index)
                except Exception as e:
                    logger.error(f"Failed to process file {file_path}: {str(e)}")
                    failed_updates += 1
    
    except Exception as e:
        logger.critical(f"Failed to process JSON files or update the database: {str(e)}")
    finally:
        if 'driver' in locals():
            driver.close()
        logger.info(f"Processed {total_files} JSON files.")
        logger.info(f"Failed to update {failed_updates} JSON files.")

# Connection details
uri = os.getenv("uri")
user = os.getenv("username")
password = os.getenv("password")

# List of directories containing the JSON files
directories = [
# Insert directory here
]

# Process the JSON files
process_json_files(directories, uri, user, password)

