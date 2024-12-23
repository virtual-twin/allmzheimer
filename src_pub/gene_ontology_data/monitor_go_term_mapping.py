import os
import sys
import time
import logging
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from src_pub.utils.logging_config import setup_logging

# Load environment variables from .env file
load_dotenv()

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Function to get the count of nodes with the affectedGoProcessId property
def count_nodes_with_go_process_id(uri, user, password):
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        result = session.run(
            "MATCH (n:Drug) WHERE n.affectedGoProcessId IS NOT NULL RETURN count(n) AS count")
        count = result.single()["count"]
        logger.info(f"Number of nodes with affectedGoProcessId: {count}")
        return count
    driver.close()

# Connection details
uri = os.getenv("uri")
user = os.getenv("username")
password = os.getenv("password")

# Monitoring interval (seconds)
monitor_interval = 60

# Monitor loop
logger.critical("Starting monitoring of nodes with affectedGoProcessId property.")

try:
    while True:
        count = count_nodes_with_go_process_id(uri, user, password)
        logger.info(f"Total nodes with affectedGoProcessId: {count}")
        time.sleep(monitor_interval)
except KeyboardInterrupt:
    logger.critical("Monitoring stopped by user.")
