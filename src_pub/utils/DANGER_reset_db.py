import logging
from dotenv import load_dotenv
import os
import sys

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from src.utils.logging_config import setup_logging
from src.utils.conn_neo4j import Neo4jConnection

def confirm_deletion(uri):
    """
    Ask the user to confirm the deletion of the entire database by typing "delete {uri}".

    Parameters
    ----------
    uri : str
        The URI of the Neo4j database.

    Returns
    -------
    bool
        True if the user confirms, False otherwise.
    """
    response = input(f"Are you sure you want to delete all nodes and relationships in the database? Type 'delete {uri}' to confirm: ").strip()
    return response == f"delete {uri}"

def check_database_empty(session):
    """
    Check if the database is empty.

    Parameters
    ----------
    session : neo4j.Session
        The Neo4j session to use for the check.

    Returns
    -------
    bool
        True if the database is empty, False otherwise.
    """
    # Check node count
    node_result = session.run("MATCH (n) RETURN COUNT(n) AS node_count").single()
    node_count = node_result["node_count"]
    logging.info(f"Node count after deletion: {node_count}")

    # Check relationship count
    relationship_result = session.run("MATCH ()-[r]->() RETURN COUNT(r) AS relationship_count").single()
    relationship_count = relationship_result["relationship_count"]
    logging.info(f"Relationship count after deletion: {relationship_count}")

    # Check index count
    index_result = session.run("SHOW INDEXES").data()
    index_count = len(index_result)
    logging.info(f"Index count after deletion: {index_count}")

    # Check constraint count
    constraint_result = session.run("SHOW CONSTRAINTS").data()
    constraint_count = len(constraint_result)
    logging.info(f"Constraint count after deletion: {constraint_count}")
    
    logging.info(f"Post-deletion check: {node_count} nodes, {relationship_count} relationships, {index_count} indexes, and {constraint_count} constraints remain in the database.")
    
    return node_count == 0 and relationship_count == 0 and index_count == 0 and constraint_count == 0


def drop_all_indexes_and_constraints(session):
    """
    Drops all indexes and constraints in the Neo4j database.

    Parameters
    ----------
    session : neo4j.Session
        The Neo4j session to use for dropping indexes and constraints.
    """
    # Drop all indexes
    indexes = session.run("SHOW INDEXES").data()
    for index in indexes:
        index_name = index['name']
        session.run(f"DROP INDEX {index_name}")
        logging.info(f"Dropped index: {index_name}")

    # Drop all constraints
    constraints = session.run("SHOW CONSTRAINTS").data()
    for constraint in constraints:
        constraint_name = constraint['name']
        session.run(f"DROP CONSTRAINT {constraint_name}")
        logging.info(f"Dropped constraint: {constraint_name}")

def delete_all_nodes():
    """
    Deletes all nodes and relationships in the Neo4j database.
    """
    # Setup environment and logging
    Neo4jConnection.setup_environment()
    setup_logging()

    # Retrieve environment variables
    uri = os.getenv("uri")
    username = os.getenv("username")
    password = os.getenv("password")

    # Confirm deletion
    if confirm_deletion(uri):
        logging.info("User confirmed deletion. Proceeding with deletion.")
        
        # Establish connection to the database
        with Neo4jConnection(uri, username, password) as conn:
            try:
                with conn.driver.session() as session:
                    # Log the start of the deletion process
                    logging.info("Starting the deletion of all nodes and relationships.")
                    
                    # Execute Cypher query to delete all nodes and relationships
                    session.run("MATCH (n) DETACH DELETE n")
                    
                    # Log the successful deletion
                    logging.info("All nodes and relationships have been successfully deleted.")
                    
                    # Drop all indexes and constraints
                    logging.info("Dropping all indexes and constraints.")
                    drop_all_indexes_and_constraints(session)
                    
                    # Check if the database is empty
                    if check_database_empty(session):
                        logging.info("The database is now empty.")
                    else:
                        logging.warning("The database is not empty after the deletion operation.")
            except Exception as e:
                logging.error(f"An error occurred while deleting nodes: {e}")
                raise
    else:
        logging.info("User cancelled the deletion operation.")
        print("Deletion operation cancelled.")

if __name__ == "__main__":
    logging.critical("Initializing database deletion script. Proceed with caution!")
    delete_all_nodes()
