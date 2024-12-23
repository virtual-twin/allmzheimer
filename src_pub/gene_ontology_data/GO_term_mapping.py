import os
import sys
import requests
import logging
import time
from neo4j import GraphDatabase, basic_auth
from dotenv import load_dotenv
from requests.exceptions import RequestException
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from src_pub.utils.logging_config import setup_logging

# Load environment variables from .env file
load_dotenv()

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 4
BACKOFF_FACTOR = 2
MAX_WORKERS = 10  # Number of threads to use

def create_driver(uri, user, password):
    return GraphDatabase.driver(
        uri, 
        auth=basic_auth(user, password),
        max_connection_lifetime=30*60,  # 30 minutes
        max_connection_pool_size=50,   # Adjust as needed
        connection_timeout=300,        # 5 minutes
        encrypted=False  # Set to True if using encryption
    )
# Function to get GO term ID from EBI QuickGO API
def get_go_term_id(term_name):
    url = "https://www.ebi.ac.uk/QuickGO/services/ontology/go/search"
    params = {
        'query': term_name,
        'limit': 1,  # Number of results to return
        'ontology': 'go'
    }
    headers = {
        'Accept': 'application/json'
    }

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, params=params, headers=headers)
            if response.status_code == 200:
                results = response.json()
                if results['results']:
                    go_term_id = results['results'][0]['id']
                    logger.info(f"GO term ID found for '{term_name}': {go_term_id}")
                    return go_term_id
                else:
                    logger.warning(f"No GO term ID found for '{term_name}'")
                    return None
            else:
                logger.error(f"Failed to fetch GO term ID for '{term_name}', status code: {response.status_code}")
                return None
        except RequestException as e:
            wait_time = BACKOFF_FACTOR ** attempt
            logger.error(f"Request failed (attempt {attempt + 1}/{MAX_RETRIES}) for '{term_name}': {e}. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)

    logger.critical(f"All retry attempts failed for '{term_name}'")
    return None

# Function to process a single node with retry logic
def process_single_node_with_retry(record, session):
    node = record['n']
    node_id = node.id

    # Check if the node already has 'affectedGoProcessId' property
    if 'affectedGoProcessId' in node and node['affectedGoProcessId'] is not None:
        logger.info(f"Node {node_id} already has 'affectedGoProcessId' property. Skipping...")
        return

    affected_go_processes = node['affectedGoProcess']
    logger.info(f"Node {node_id} affectedGoProcess: {affected_go_processes}")
    go_term_ids = []
    processes = []

    if isinstance(affected_go_processes, str):
        processes = affected_go_processes.split(',')
    elif isinstance(affected_go_processes, list):
        processes = affected_go_processes

    for process in processes:
        process = process.strip()
        go_term_id = get_go_term_id(process)
        if go_term_id:
            go_term_ids.append(go_term_id)

    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"Updating node {node_id} with GO term IDs: {go_term_ids}")
            update_result = session.run(
                "MATCH (n) WHERE id(n)=$id SET n.affectedGoProcessId = $go_term_ids RETURN n", 
                id=node_id, go_term_ids=go_term_ids)
            if update_result.single() is not None:
                logger.info(f"Successfully updated node {node_id} with affectedGoProcessId.")
                return
            else:
                logger.error(f"Failed to update node {node_id}.")
                return
        except Exception as e:
            wait_time = BACKOFF_FACTOR ** attempt
            logger.error(f"Error updating node {node_id} (attempt {attempt + 1}/{MAX_RETRIES}): {e}. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
    logger.critical(f"All retry attempts failed for updating node {node_id}")

# Function to process nodes in Neo4j in batches
def process_nodes_in_batches(uri, user, password, batch_size=50):
    driver = create_driver(uri, user, password)
    with driver.session() as session:
        logger.info("Running query to count nodes with label 'Drug' and non-null, non-empty 'affectedGoProcess' property.")
        count_result = session.run("MATCH (n:Drug) WHERE n.affectedGoProcess IS NOT NULL AND size(n.affectedGoProcess) > 0 RETURN count(n) AS count")
        total_nodes = count_result.single()["count"]
        logger.info(f"Total nodes to process: {total_nodes}")

        total_batches = (total_nodes // batch_size) + 1
        for batch in range(total_batches):
            logger.info(f"Processing batch {batch + 1} of {total_batches}")
            try:
                result = session.run(
                    "MATCH (n:Drug) WHERE n.affectedGoProcess IS NOT NULL AND size(n.affectedGoProcess) > 0 "
                    "RETURN n SKIP $skip LIMIT $limit",
                    skip=batch * batch_size, limit=batch_size)
            except Exception as e:
                logger.error(f"Error executing query for batch {batch + 1}: {e}")
                time.sleep(10)  # Wait before retrying
                continue

            nodes_processed = 0
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_to_record = {executor.submit(process_single_node_with_retry, record, session): record for record in result}
                for future in as_completed(future_to_record):
                    record = future_to_record[future]
                    try:
                        future.result()
                        nodes_processed += 1
                    except Exception as e:
                        logger.error(f"Error processing node {record['n'].id}: {e}")

            logger.info(f"Batch {batch + 1} processed: {nodes_processed} nodes")

    driver.close()


# Connection details
uri = os.getenv("uri")
user = os.getenv("username")
password = os.getenv("password")

# Process the nodes in batches
logger.critical("Initializing script for adding ARUK-UCL biological processes to Neo4j.")
process_nodes_in_batches(uri, user, password, batch_size=50)
