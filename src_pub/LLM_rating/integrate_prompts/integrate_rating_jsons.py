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

def update_drug_node(session, drugbank_id, response_json, token_length, index):
    try:
        logger.debug(f"response_json type: {type(response_json)}")
        logger.debug(f"response_json content: {response_json}")

        if isinstance(response_json, str):
            logger.error("response_json is still a string, skipping update.")
            return

        reason_rating = response_json.get('reason_rating', '')
        rating = response_json.get('rating', 0.0)

        # Create property names with suffix based on directory index
        reason_rating_property = f"reason_rating_{index}"
        rating_property = f"rating_{index}"
        rating_token_length_property = f"rating_token_length_{index}"

        session.run(f"""
            MATCH (d:Drug {{drugbankId: $drugbank_id}})
            SET d.{reason_rating_property} = $reason_rating,
                d.{rating_property} = $rating,
                d.{rating_token_length_property} = $token_length
            RETURN d
        """, drugbank_id=drugbank_id, reason_rating=reason_rating, rating=rating, token_length=token_length)

        # Verify the update
        result = session.run(f"""
            MATCH (d:Drug {{drugbankId: $drugbank_id}})
            RETURN d.{reason_rating_property} AS reason_rating, d.{rating_property} AS rating, d.{rating_token_length_property} AS rating_token_length
        """, drugbank_id=drugbank_id)

        record = result.single()
        if record:
            logger.info(f"Updated Drug node with drugbankId: {drugbank_id}")
            logger.info(f"{reason_rating_property}: {record['reason_rating']}")
            logger.info(f"{rating_property}: {record['rating']}")
            logger.info(f"{rating_token_length_property}: {record['rating_token_length']}")
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

                    if isinstance(response_json, str):
                        try:
                            response_json = json.loads(response_json)
                            logger.debug(f"Re-parsed response_json type: {type(response_json)}")
                            logger.debug(f"Re-parsed response_json content: {response_json}")
                        except json.JSONDecodeError as e:
                            logger.error(f"Second JSON decode error in file {file_path}: {str(e)}")
                            failed_updates += 1
                            continue

                    if not isinstance(response_json, dict):
                        logger.error(f"response_json is not a dictionary even after re-parsing in file {file_path}")
                        failed_updates += 1
                        continue

                    # Extract drugbank_id from filename and handle special characters
                    drugbank_id = json_file.split('_')[-1].replace('.json', '')
                    
                    # Call update_drug_node for each JSON file
                    with driver.session() as session:
                        # Calculate token length (assuming response_data is the prompt for token length)
                        token_length = len(response_data)
                        update_drug_node(session, drugbank_id, response_json, token_length, index)
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
# Provide your directories here
directories = [
]

# Process the JSON files
process_json_files(directories, uri, user, password)
