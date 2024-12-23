import os
import sys
from neo4j import GraphDatabase
from dotenv import load_dotenv
import logging

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from src_pub.utils.logging_config import setup_logging
from src_pub.utils.conn_neo4j import Neo4jConnection
from src_pub.utils.uuid_util import generate_uuid

# Load environment variables from .env file
load_dotenv()

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

def connect_drug_to_biological_process(uri, user, password):
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info("Database connection established successfully.")

        with driver.session() as session:
            logger.info("Starting to find Drug nodes with non-empty affectedGoProcessId property.")
            
            # Find drug nodes with non-empty affectedGoProcessId property
            drug_nodes_result = session.run("""
                MATCH (d:Drug)
                WHERE size(d.affectedGoProcessId) > 0
                RETURN d
            """)

            if drug_nodes_result.peek() is None:
                logger.warning("No Drug nodes found with non-empty affectedGoProcessId property.")
                return

            nodes_processed = 0
            for record in drug_nodes_result:
                drug_node = record['d']
                drugbank_id = drug_node.get('drugbankId', None)
                
                if not drugbank_id:
                    logger.warning(f"Drug node without drugbankId found: {drug_node.id} with properties: {drug_node.items()}")
                    continue

                affected_go_process_ids = drug_node.get('affectedGoProcessId', [])
                
                logger.info(f"Processing Drug node {drugbank_id} with affectedGoProcessId: {affected_go_process_ids}")

                # Check if affectedGoProcessId is a list
                if isinstance(affected_go_process_ids, list):
                    for go_term_id in affected_go_process_ids:
                        # Ensure the go_term_id is properly trimmed
                        go_term_id = go_term_id.strip()
                        result = session.run("""
                            MATCH (b:BiologicalProcess {goTerm: $go_term_id})
                            WITH b
                            MATCH (d:Drug {drugbankId: $drugbank_id})
                            MERGE (d)-[:AFFECTS]->(b)
                            RETURN b
                        """, drugbank_id=drugbank_id, go_term_id=go_term_id)
                        
                        summary = result.consume()
                        if summary.counters.contains_updates:
                            logger.critical(f"Connected Drug node {drugbank_id} to BiologicalProcess with goTerm: {go_term_id}")
                        else:
                            logger.info(f"No BiologicalProcess node found with goTerm: {go_term_id} for Drug node {drugbank_id}")

                    nodes_processed += 1
                else:
                    logger.warning(f"Drug node {drugbank_id} affectedGoProcessId is not a list: {affected_go_process_ids}")

            logger.info(f"Completed processing all Drug nodes. Total nodes processed: {nodes_processed}")

    except Exception as e:
        logger.critical(f"Failed to establish database connection: {str(e)}")
    finally:
        if 'driver' in locals():
            driver.close()

# Connection details
uri = os.getenv("uri")
user = os.getenv("username")
password = os.getenv("password")

# Connect drug nodes to biological process nodes
logger.info("Initializing script for connecting Drug nodes to BiologicalProcess nodes.")
connect_drug_to_biological_process(uri, user, password)