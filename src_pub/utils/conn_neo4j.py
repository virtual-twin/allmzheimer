"""
This module provides a standard connection class for interacting with the Neo4j database of this project.

Example usage:
    from conn_neo4j import Neo4jConnection

    Neo4jConnection.setup_environment()
    with Neo4jConnection(URI, USERNAME, PASSWORD) as conn:
        conn.give_graph_summary()
"""

from dotenv import load_dotenv
import os





# Example usage is at the bottom of the file

import logging
import rdflib
from dotenv import load_dotenv, find_dotenv
import os
from neo4j import GraphDatabase, basic_auth


# Environment variables
load_dotenv()
uri = os.getenv("uri")
username = os.getenv("username")
password = os.getenv("password")
# ONTOLOGY_PATH = os.getenv("ontology_path") # Adjust this for each ontology in the end


class Neo4jConnection:
    """
    A class to manage connections to a Neo4j database.

    Attributes
    ----------
    uri : str
        The URI of the Neo4j database. Imported from environment variables.
    user : str
        The username for the Neo4j database. Imported from environment variables.
    password : str
        The password for the Neo4j database. Imported from environment variables.
    driver : neo4j.Driver
        The driver instance for the Neo4j database connection.

    Methods
    -------
    connect():
        Establishes a connection to the Neo4j database.
    close():
        Closes the connection to the Neo4j database.
    give_graph_summary():
        Prints a summary of the graph.
    check_graph_empty():
        Checks if the graph is empty.
    setup_environment():
        Sets up the environment by loading environment variables and configuring logging.
    """
        
    def __init__(self, uri, user, password):
        """
        Constructs all the necessary attributes for the Neo4jConnection object.

        Parameters
        ----------
        uri : str
            The URI of the Neo4j database.
        user : str
            The username for the Neo4j database.
        password : str
            The password for the Neo4j database.
        """
        logging.info("Running Neo4jConnection constructor")
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = None
        self.connect()
            
    def connect(self):
        """
        Establishes a connection to the Neo4j database.

        Raises
        ------
        Exception
            If the connection to the Neo4j database cannot be established.
        """
        try:
            logging.info("Establishing connection to Neo4j db")
            self.driver = GraphDatabase.driver(self.uri, auth=basic_auth(self.user, self.password))
            logging.info("Connection to Neo4j db established")
        except Exception as e:
            logging.error(f"Falied to establish connection to Neo4j db: {e}")
            raise
            
    def close(self):
        """
        Closes the connection to the Neo4j database.

        Raises
        ------
        Exception
            If the connection to the Neo4j database cannot be closed.
        """
        if self.driver:
            try:
                logging.info("Closing connection to Neo4j db")
                self.driver.close()
                logging.info("Connection to Neo4j db closed")
            except Exception as e:
                logging.error(f"Failed to close connection to Neo4j db: {e}")
                raise
    
    def __enter__(self):
        """
        Enters the runtime context related to this object.

        Returns
        -------
        Neo4jConnection
            The Neo4jConnection object itself.
        """
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        """
        Exits the runtime context related to this object.

        Parameters
        ----------
        exc_type : type
            The exception type.
        exc_value : Exception
            The exception instance.
        traceback : traceback
            The traceback object.
        """
        self.close()

    def give_graph_summary(self):
        """
        Prints a summary of the graph.

        Raises
        ------
        Exception
            If there is an error while printing the graph summary.
        """
        try:
            counts = self.check_graph_empty()
            if counts:
                node_count = counts['node_count']
                relationship_count = counts['relationship_count']
                if node_count == 0 and relationship_count == 0:
                    logging.warning("Graph is empty")
                else:
                    logging.info(f"Graph contains {node_count} nodes and {relationship_count} relationships")
            else:
                logging.warning("Failed to retrieve data from graph")
        except Exception as e:
            logging.error(f'Error while printing graph summary: {e}')
            raise

    def check_graph_empty(self):
        """
        Checks if the graph is empty.

        Returns
        -------
        dict
            A dictionary with the counts of nodes and relationships in the graph.
             The dictionary contains:
            - 'node_count': int
                The number of nodes in the graph.
            - 'relationship_count': int
                The number of relationships in the graph.

        """
        return {'node_count': 0, 'relationship_count': 0}
    
    @staticmethod
    def setup_environment():
        """
        Sets up the environment by loading environment variables and configuring logging.

        Raises
        ------
        FileNotFoundError
            If the .env file is not found.
        EnvironmentError
            If any required environment variable is not set.
        """
        if not find_dotenv():
            logging.error("No .env file found")
            raise FileNotFoundError("No .env file found")
        load_dotenv()
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        required_vars = ['uri', 'username', 'password'] # Maybe add ontology path here later 
        for var in required_vars:
            if not os.getenv(var):
                logging.error(f"Environment variable {var} not set")
                raise EnvironmentError(f"Environment variable {var} not set")

# # Example usage
# if __name__ == "__main__":
#     try:
#         Neo4jConnection.setup_environment()
#         URI = os.getenv("uri")
#         USERNAME = os.getenv("username")
#         PASSWORD = os.getenv("password")
#         with Neo4jConnection(URI, USERNAME, PASSWORD) as conn:
#             conn.print_graph_summary()
#     except Exception as e:
#         logging.error(f"An error occurred: {e}")