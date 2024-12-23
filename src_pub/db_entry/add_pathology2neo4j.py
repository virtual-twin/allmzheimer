import sys 
import os
import logging




# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from src_pub.utils.logging_config import setup_logging
from src_pub.utils.conn_neo4j import Neo4jConnection
from src_pub.utils.uuid_util import generate_uuid

class PathologyNeo4j:
    def __init__(self, driver):
        self.driver = driver

    def create_alzheimer_node(self):
        """
        Create a node with pathologyName 'Pathology' and pathologyName 'Alzheimer'.
        """
        uuid = generate_uuid()
        query = "MERGE (p:Pathology {pathologyName: 'Alzheimer'}) ON CREATE SET p.uuid = $uuid RETURN p"
        with self.driver.session() as session:
            session.run(query, uuid=uuid)
        logging.info("Alzheimer node created or already exists.")

    def connect_biological_processes_to_alzheimer(self):
        """
        Connect all nodes with label 'BiologicalProcess' to the 'Alzheimer' node.
        """
        query = """
        MATCH (p:Pathology {pathologyName: 'Alzheimer'})
        MATCH (b:BiologicalProcess)
        MERGE (b)-[:RELATED_TO]->(p)
        """
        with self.driver.session() as session:
            session.run(query)
        logging.info("All BiologicalProcess nodes connected to Alzheimer node.")

    def connect_proteins_to_alzheimer(self): # Not required in current script since proteins are left out
        """
        Connect all nodes with label 'Protein' to the 'Alzheimer' node.
        """
        query = """
        MATCH (p:Pathology {pathologyName: 'Alzheimer'})
        MATCH (pr:Protein)
        MERGE (pr)-[:RELATED_TO]->(p)
        """
        with self.driver.session() as session:
            session.run(query)
        logging.info("All Protein nodes connected to Alzheimer node.")

    def verify_connections(self):
        """
        Verify that all BiologicalProcess and Protein nodes are connected to the Alzheimer node.
        """
        query = """
        MATCH (n)
        WHERE (n:BiologicalProcess OR n:Protein) AND NOT (n)-[:RELATED_TO]->(:Pathology {pathologyName: 'Alzheimer'})
        RETURN n, labels(n) AS unconnected_labels
        """
        with self.driver.session() as session:
            result = session.run(query)
            unconnected_nodes = result.data()
            unconnected_count = len(unconnected_nodes)
            if unconnected_count == 0:
                logging.info("All BiologicalProcess and Protein nodes are connected to the Alzheimer node.")
            else:
                logging.warning(f"There are {unconnected_count} nodes not connected to the Alzheimer node.")
                for node in unconnected_nodes:
                    node_properties = node['n']
                    logging.warning(f"Unconnected node properties: {node_properties} with labels {node['unconnected_labels']}")
                    self.retry_connection(node_properties)
    
    def retry_connection(self, node_properties): # Is this function even needed? Also it might cause issues by using the internal id
        """
        Retry connecting a node to the Alzheimer node.
        """
        query = """
        MATCH (p:Pathology {pathologyName: 'Alzheimer'})
        MATCH (n {id: $id})
        MERGE (n)-[:RELATED_TO]->(p)
        """
        with self.driver.session() as session:
            session.run(query, id=node_properties['id'])
        logging.info(f"Retried connection for node with id: {node_properties['id']}")
    
    def test_pathology_connection(self):
        """
        Test the number of nodes and the number of relationships of the Alzheimer node.
        This is done by comparing the number of relationships of the Alzheimer node to the total number of nodes.
        The total number of nodes should be equal to the number of relationships of the Alzheimer node minus one (because the pathology node is not connected to itself).
        """
        total_nodes_query = "MATCH (n) RETURN count(n) AS total_nodes"
        alzheimer_connections_query = """
        MATCH (p:Pathology {pathologyName: 'Alzheimer'})-[r:RELATED_TO]-()
        RETURN count(r) AS alzheimer_connections
        """
        
        with self.driver.session() as session:
            total_nodes_result = session.run(total_nodes_query).single()
            alzheimer_connections_result = session.run(alzheimer_connections_query).single()
        
        total_nodes = total_nodes_result['total_nodes']
        alzheimer_connections = alzheimer_connections_result['alzheimer_connections']

        logging.info(f"Total nodes in the database: {total_nodes}")
        logging.info(f"Connections of the Alzheimer node: {alzheimer_connections}")

        if alzheimer_connections == total_nodes - 1:
            logging.info("Based on the relationships of the Alzheimer node compared to total number of nodes - All nodes are connected with the pathology.")
        else:
            logging.warning("There are nodes not connected to the Alzheimer node.")


        

def add_pathology():
    
    setup_logging()  # Initialize logging
    Neo4jConnection.setup_environment()
    uri = os.getenv("uri")
    user = os.getenv("username")
    password = os.getenv("password")

    try:
          with Neo4jConnection(uri, user, password) as conn:
            pathology_neo4j = PathologyNeo4j(conn.driver)
            pathology_neo4j.create_alzheimer_node()
            pathology_neo4j.connect_biological_processes_to_alzheimer()
            pathology_neo4j.connect_proteins_to_alzheimer()
            pathology_neo4j.verify_connections()
            pathology_neo4j.test_pathology_connection()
    except Exception as e:
        logging.error(f"An error occurred: {e}")

if __name__ == "__main__":
    logging.critical("Initializing script for adding the pathology to Neo4j.")
    add_pathology()