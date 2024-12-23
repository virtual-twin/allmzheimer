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

def remove_unconnected_drug_nodes(uri, user, password):
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info("Database connection established successfully.")

        with driver.session() as session:
            logger.info("Starting to find and remove Drug nodes with no 'AFFECTS' relationship to BiologicalProcess nodes.")
            
            # Find drug nodes with no 'AFFECTS' relationship
            unconnected_drug_nodes_result = session.run("""
                MATCH (d:Drug)
                WHERE NOT (d)-[:AFFECTS]->(:BiologicalProcess)
                RETURN d
            """)

            if unconnected_drug_nodes_result.peek() is None:
                logger.warning("No unconnected Drug nodes found.")
                return

            nodes_removed = 0
            nodes_kept = 0
            for record in unconnected_drug_nodes_result:
                drug_node = record['d']
                drugbank_id = drug_node.get('drugbankId', None)
                
                if not drugbank_id:
                    logger.warning(f"Drug node without drugbankId found: {drug_node.id} with properties: {drug_node.items()}")
                    continue

                logger.info(f"Removing unconnected Drug node with drugbankId: {drugbank_id}")

                # Remove the unconnected drug node
                session.run("""
                    MATCH (d:Drug {drugbankId: $drugbank_id})
                    DETACH DELETE d
                """, drugbank_id=drugbank_id)

                nodes_removed += 1
                logger.info(f"Removed Drug node with drugbankId: {drugbank_id}")

            # Count nodes that were kept
            connected_drug_nodes_result = session.run("""
                MATCH (d:Drug)
                WHERE (d)-[:AFFECTS]->(:BiologicalProcess)
                RETURN count(d) as count
            """)

            nodes_kept = connected_drug_nodes_result.single()['count']
            logger.critical(f"Total nodes removed: {nodes_removed}")
            logger.critical(f"Total nodes kept: {nodes_kept}")

    except Exception as e:
        logger.critical(f"Failed to establish database connection or remove nodes: {str(e)}")
    finally:
        if 'driver' in locals():
            driver.close()

# Connection details
uri = os.getenv("uri")
user = os.getenv("username")
password = os.getenv("password")

# Remove unconnected drug nodes
logger.info("Initializing script for removing unconnected Drug nodes.")
remove_unconnected_drug_nodes(uri, user, password)
