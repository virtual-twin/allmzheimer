import os
import sys
import time
from neo4j import GraphDatabase
from dotenv import load_dotenv
import logging

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from src_pub.utils.logging_config import setup_logging
from src_pub.utils.conn_neo4j import Neo4jConnection

# Load environment variables from .env file
load_dotenv()

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

def monitor_connections(uri, user, password):
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info("Monitoring script: Database connection established successfully.")

        while True:
            with driver.session() as session:
                logger.info("Monitoring script: Checking number of connections and unique nodes between Drug and BiologicalProcess nodes.")
                
                result = session.run("""
                    MATCH (d:Drug)-[:AFFECTS]->(b:BiologicalProcess)
                    RETURN count(*) AS connection_count,
                           count(distinct d) AS drug_count,
                           count(distinct b) AS bio_process_count
                """)
                
                record = result.single()
                connection_count = record['connection_count']
                drug_count = record['drug_count']
                bio_process_count = record['bio_process_count']
                
                logger.info(f"Monitoring script: Number of connections found: {connection_count}")
                logger.info(f"Monitoring script: Number of unique Drug nodes involved: {drug_count}")
                logger.info(f"Monitoring script: Number of unique BiologicalProcess nodes involved: {bio_process_count}")
            
            logger.info("Monitoring script: Sleeping for 60 seconds.")
            time.sleep(60)

    except Exception as e:
        logger.critical(f"Monitoring script: Failed to establish database connection: {str(e)}")
    finally:
        if 'driver' in locals():
            driver.close()

# Connection details
uri = os.getenv("uri")
user = os.getenv("username")
password = os.getenv("password")

# Start monitoring connections
logger.info("Monitoring script: Initializing script for monitoring connections between Drug nodes and BiologicalProcess nodes.")
monitor_connections(uri, user, password)
