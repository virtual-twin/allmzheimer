import os
import sys
import logging
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.utils.logging_config import setup_logging

class Neo4jUUIDTest:
    """
    A class to manage the connection to a Neo4j database and provide methods to test UUID presence in nodes.

    Methods:
        __init__(self, uri, user, password): Initializes the connection to the Neo4j database.
        close(self): Closes the connection to the Neo4j database.
        test_uuid_presence(self): Tests if all nodes have a UUID and logs the results.
    """
    def __init__(self, uri, user, password):
        """
        Initialize the connection to the Neo4j database.

        Args:
            uri (str): The URI of the Neo4j database.
            user (str): The username for the Neo4j database.
            password (str): The password for the Neo4j database.
        """
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        
    def close(self):
        """
        Close the connection to the Neo4j database.
        """
        self.driver.close()

    def test_uuid_presence(self):
        """
        Test if all nodes have a UUID and log the results.

        This function checks for the presence of the 'uuid' property in all nodes.
        It logs the total number of nodes checked, the number of nodes without a UUID,
        and raises a critical log message if any nodes are found without a UUID.
        """
        logging.info("Starting UUID presence test.")
        query = (
            "MATCH (n) WHERE n.uuid IS NULL "
            "RETURN count(n) AS nodesWithoutUUID"
        )
        with self.driver.session() as session:
            result = session.run(query)
            nodes_without_uuid = result.single()['nodesWithoutUUID']
            logging.info(f"UUID presence test completed. Nodes without UUID: {nodes_without_uuid}")

            if nodes_without_uuid > 0:
                logging.critical(f"CRITICAL: {nodes_without_uuid} nodes are missing the UUID property!")

if __name__ == "__main__":
    # Load environment variables & configure logging
    def setup_environment():
        """
        Load environment variables and configure logging.
        """
        load_dotenv('.env')
        setup_logging()

    setup_environment()

    # Initialize Neo4j test connection
    neo4j_test = Neo4jUUIDTest(
        uri=os.getenv("uri"),
        user=os.getenv("username"),
        password=os.getenv("password")
    )

    # Run the UUID presence test
    neo4j_test.test_uuid_presence()

    # Close the Neo4j connection
    neo4j_test.close()
