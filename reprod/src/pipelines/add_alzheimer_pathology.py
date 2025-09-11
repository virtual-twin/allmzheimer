# file: src/pipelines/add_alzheimer_pathology.py

import sys
import os
import logging


project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.logging_config import setup_logging
from src.utils.conn_neo4j import Neo4jConnection
from src.utils.uuid_util import generate_uuid

class PathologyNeo4j:
    def __init__(self, driver):
        self.driver = driver

    def _ensure_constraints(self):
        """
        Ensure idempotent uniqueness on :Pathology(pathologyName).
        """
        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    "CREATE CONSTRAINT pathology_name IF NOT EXISTS "
                    "FOR (p:Pathology) REQUIRE p.pathologyName IS UNIQUE"
                )
            )
        logging.info("Constraint ensured: :Pathology(pathologyName UNIQUE)")

    def create_alzheimer_node(self):
        """
        Create a node with pathologyName 'Alzheimer'.
        """
        uuid = generate_uuid()
        query = (
            "MERGE (p:Pathology {pathologyName: 'Alzheimer'}) "
            "ON CREATE SET p.uuid = $uuid "
            "RETURN p"
        )
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
            summary = session.run(query).consume().counters
        logging.info(
            "BiologicalProcess→Alzheimer relationships ensured "
            "(relationships_created=%d, properties_set=%d).",
            summary.relationships_created, summary.properties_set
        )

    def verify_connections(self):
        """
        Verify that all BiologicalProcess nodes are connected to the Alzheimer node.
        """
        query = """
        OPTIONAL MATCH (b:BiologicalProcess)
        WITH coalesce(count(CASE WHEN NOT (b)-[:RELATED_TO]->(:Pathology {pathologyName: 'Alzheimer'}) THEN 1 END), 0) AS unconnected_bio
        RETURN unconnected_bio
        """
        with self.driver.session() as session:
            rec = session.run(query).single()

        un_bio = int(rec.get("unconnected_bio", 0)) if rec else 0
        logging.info("Unconnected BiologicalProcess nodes: %d", un_bio)
        if un_bio == 0:
            logging.info("All BiologicalProcess nodes are connected to the Alzheimer node.")
        else:
            logging.warning("There are %d BiologicalProcess nodes not connected to the Alzheimer node.", un_bio)

    def test_pathology_connection(self):
        """
        Test coverage specifically for BiologicalProcess nodes:
        Compare the number of BiologicalProcess nodes to the number of
        (:BiologicalProcess)-[:RELATED_TO]->(:Pathology {Alzheimer}) relationships.
        """
        total_bio_query = "MATCH (b:BiologicalProcess) RETURN count(b) AS total_bio"
        alz_bio_rel_query = """
        MATCH (:BiologicalProcess)-[r:RELATED_TO]->(:Pathology {pathologyName: 'Alzheimer'})
        RETURN count(r) AS rels
        """
        with self.driver.session() as session:
            total_bio = int(session.run(total_bio_query).single()["total_bio"])
            rels = int(session.run(alz_bio_rel_query).single()["rels"])

        logging.info("Total BiologicalProcess nodes: %d", total_bio)
        logging.info("Alzheimer-related BiologicalProcess relationships: %d", rels)

        if rels == total_bio:
            logging.info("Alzheimer pathology relationships cover all BiologicalProcess nodes.")
        else:
            logging.warning(
                "Alzheimer pathology relationships (%d) do not cover all BiologicalProcess nodes (%d).",
                rels, total_bio
            )

def _resolve_creds():
    """
    Resolve Neo4j credentials from env (container-safe), with NEO4J_AUTH fallback.
    """
    uri = os.getenv("uri", "bolt://neo4j:7687")
    user = os.getenv("username", "neo4j")
    pwd = os.getenv("password")
    if not pwd and os.getenv("NEO4J_AUTH", "").startswith("neo4j/"):
        pwd = os.getenv("NEO4J_AUTH")[len("neo4j/"):]
    if not pwd:
        raise RuntimeError("Neo4j password not provided via 'password' or NEO4J_AUTH.")
    return uri, user, pwd

def add_pathology():
    setup_logging()
    uri, user, password = _resolve_creds()

    try:
        with Neo4jConnection(uri, user, password) as conn:
            pathology_neo4j = PathologyNeo4j(conn.driver)
            pathology_neo4j._ensure_constraints()
            pathology_neo4j.create_alzheimer_node()
            pathology_neo4j.connect_biological_processes_to_alzheimer()
            pathology_neo4j.verify_connections()
            pathology_neo4j.test_pathology_connection()
    except Exception as e:
        logging.error("An error occurred: %s", e)
        raise

if __name__ == "__main__":
    logging.critical("Initializing script for adding the pathology to Neo4j.")
    add_pathology()