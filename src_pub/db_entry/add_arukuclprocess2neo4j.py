"""
This module provides functionality to add biological processes selected by ARUK-UCL to the Neo4j database.

Functions:
    setup_environment(): Load environment variables and configure logging.
    add_arukucl_to_neo4j_db(): Function to load data and add biological processes to Neo4j.

Classes:
    Neo4jConnectionExtended: Extends Neo4jConnection to add biological processes.
"""


# Function to add biological process to neo4j database

import os
import sys
import pandas as pd
import logging
from dotenv import load_dotenv
import pandas as pd

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from src_pub.utils.logging_config import setup_logging
from src_pub.utils.conn_neo4j import Neo4jConnection
from src_pub.utils.uuid_util import generate_uuid

TSV_FILE_PATH = os.getenv('BIOPROCESS_ARUK_UCL_GO_TERMS_TSV', 'datasets/ARUK-UCL-GO-terms.tsv') # 'datasets/ARUK-UCL-GO-terms.tsv' default if it fails

# Load environment variables & configure logging
def setup_environment():
    """
    Load environment variables and configure logging.
    """
    

class Neo4jConnectionExtended(Neo4jConnection):
    """
    Extends Neo4jConnection to add biological processes.

    Methods
    -------
    add_biological_process(data: pd.DataFrame):
        Adds biological processes to the Neo4j database.
    
    TO DO:
    - Rename this class since its name is ambigous and not descriptive

    """

    def add_biological_process(self, data):
        """
        Add biological processes to the Neo4j database.

        Parameters
        ----------
        data : pd.DataFrame
            DataFrame containing biological process data.
        """
        logging.info("Starting to add biological processes to Neo4j.")
        with self.driver.session() as session:
            nodes_not_created = 0 # Actually counts the number of nodes created, fix this misleading name that originated from an earlier version of the code
            nodes_merged = 0
            for index, row in data.iterrows():
                logging.debug(f"Adding biological process: {row['GO NAME']}")
                result = session.execute_write(self._create_or_update_biological_process, row)
                if result['created']:
                    nodes_not_created += 1 # Actually counts the number of nodes created, fix this misleading name that originated from an earlier version of the code
                else:
                    nodes_merged += 1
            logging.info(f"Finished adding biological processes to Neo4j. Nodes not created: {nodes_not_created}, Nodes merged: {nodes_merged}")

    @staticmethod
    
    def _create_or_update_biological_process(tx, row):
        """
        Create and return a biological process node in Neo4j.

        TO DO:
        Be aware - at the moment the code takes each column name in the Dataframe (except 'GO Name') 
        and uses it as key for the node.
        This has the potential of making the properties very messy. 
        Therefore, we need to hardcode the column names here.
        This title should follow camelCase, have no spaces and needs to be congruent with the other dfs.

        New name for "GO TERM" (which is based on the "GO TERM" column) - 'goTerm'

        Parameters
        ----------
        tx : neo4j.Transaction
            The transaction context to run the query.
        row : pd.Series
            A row of data containing biological process attributes.

        Returns
        -------
        neo4j.graph.Node
            The created biological process node.
        """
        # Mapping of DataFrame column names to Neo4j property names
        property_mapping = {
            'GENE PRODUCT DB': 'geneProductDb',
            'GENE PRODUCT ID': 'geneProductId',
            'SYMBOL': 'symbol',  # this property needs renaming - but first we need to find out what it actually means
            'QUALIFIER': 'qualifier',
            'GO TERM': 'goTerm',
            'GO NAME': 'goName',
            'ECO ID': 'ecoId',
            'GO EVIDENCE CODE': 'goEvidenceCode',
            'REFERENCE': 'reference',
            'WITH/FROM': 'withFrom',
            'TAXON ID': 'taxonId',
            'ASSIGNED BY': 'assignedBy',
            'ANNOTATION EXTENSION': 'annotationExtension',
            'GO ASPECT': 'goAspect',
        }

        # Create the attributes dictionary based on the mapping
        attributes = {}
        missing_columns = []
        for col, neo4j_prop in property_mapping.items():
            if col in row:
                attributes[neo4j_prop] = row[col]
                logging.debug(f"Set attribute '{neo4j_prop}' to '{row[col]}'")
            else:
                missing_columns.append(col)

        # Log missing columns
        if missing_columns:
            logging.warning(f"Missing columns for row {row.name}: {', '.join(missing_columns)}")

        # Set the label property to be the same as goName
        if 'GO NAME' in row:
            attributes['label'] = row['GO NAME']
        else:
            logging.error("Critical column 'GO NAME' is missing. This node will not have a label.")
        
        # Add unique identifier
        try:
            uuid = generate_uuid()
            attributes['uuid'] = uuid
            logging.debug(f"Generated and set attribute 'uuid' to '{uuid}'")
        except Exception as e:
            logging.error(f"Failed to generate UUID: {e}")
            raise

        # Check for critical columns
        critical_columns = ['GO NAME', 'GO TERM']
        for critical in critical_columns:
            if critical not in row:
                logging.error(f"Critical column '{critical}' is missing. Node creation may be incomplete.")

        merge_query = (
            "MERGE (b:BiologicalProcess {goTerm: $goTerm}) "
            "ON CREATE SET b += $attributes "
            "ON MATCH SET "
            "b.geneProductDb = CASE WHEN b.geneProductDb IS NULL THEN $attributes.geneProductDb ELSE b.geneProductDb + ', ' + $attributes.geneProductDb END, "
            "b.geneProductId = CASE WHEN b.geneProductId IS NULL THEN $attributes.geneProductId ELSE b.geneProductId + ', ' + $attributes.geneProductId END, "
            "b.symbol = CASE WHEN b.symbol IS NULL THEN $attributes.symbol ELSE b.symbol + ', ' + $attributes.symbol END, "
            "b.qualifier = CASE WHEN b.qualifier IS NULL THEN $attributes.qualifier ELSE b.qualifier + ', ' + $attributes.qualifier END, "
            "b.ecoId = CASE WHEN b.ecoId IS NULL THEN $attributes.ecoId ELSE b.ecoId + ', ' + $attributes.ecoId END, "
            "b.goEvidenceCode = CASE WHEN b.goEvidenceCode IS NULL THEN $attributes.goEvidenceCode ELSE b.goEvidenceCode + ', ' + $attributes.goEvidenceCode END, "
            "b.reference = CASE WHEN b.reference IS NULL THEN $attributes.reference ELSE b.reference + ', ' + $attributes.reference END, "
            "b.withFrom = CASE WHEN b.withFrom IS NULL THEN $attributes.withFrom ELSE b.withFrom + ', ' + $attributes.withFrom END, "
            "b.taxonId = CASE WHEN b.taxonId IS NULL THEN $attributes.taxonId ELSE b.taxonId + ', ' + $attributes.taxonId END, "
            "b.assignedBy = CASE WHEN b.assignedBy IS NULL THEN $attributes.assignedBy ELSE b.assignedBy + ', ' + $attributes.assignedBy END, "
            "b.annotationExtension = CASE WHEN b.annotationExtension IS NULL THEN $attributes.annotationExtension ELSE b.annotationExtension + ', ' + $attributes.annotationExtension END, "
            "b.goAspect = CASE WHEN b.goAspect IS NULL THEN $attributes.goAspect ELSE b.goAspect + ', ' + $attributes.goAspect END "
            "RETURN b, EXISTS((b)-[:CREATED_BY]-()) as created"
        )

        logging.debug(f"Executing query: {merge_query} with attributes: {attributes}")
        result = tx.run(merge_query, goTerm=row['GO TERM'], attributes=attributes)
        record = result.single()
        node = record['b']
        created = record['created']
        if not created:
            logging.debug(f"Node already exists: {row['GO TERM']}")
        return {'node': node, 'created': created}

    


def add_arukucl_to_neo4j_db():
    """
    Function that adds biological processes selected by ARUK-UCL to a Neo4j database.
    """
    #### ADD only if the node is not already there - this should be based on the GO ID 
    ### The GO ID is the relevant factor that determines, if the data point is already in there
    ### However, if a GO ID is already in there, the GeneProduct relation should be added anyway since we would loose data otherwise

    setup_environment()
    setup_logging()
    
    filtered_arukucl_path = os.getenv('BIOPROCESS_ARUK_UCL_GO_TERMS_TSV')
    if not filtered_arukucl_path:
        logging.error("The environment variable 'BIOPROCESS_ARUK_UCL_GO_TERMS_TSV' is not set")
        return
    
    try:
        logging.info(f"Loading data from {filtered_arukucl_path}")
        data = pd.read_csv(filtered_arukucl_path, sep='\t')
    except Exception as e:
        logging.error(f"Failed to load data from {filtered_arukucl_path}: {e}")
        return
    
    try:
        logging.info("Initializing Neo4j connection.")
        neo4j_conn = Neo4jConnectionExtended(
            uri=os.getenv("uri"),
            user=os.getenv("username"),
            password=os.getenv("password")
        )
        logging.info("Neo4j connection initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize Neo4j connection: {e}")
        return

    try:
        neo4j_conn.add_biological_process(data)
    except Exception as e:
        logging.error(f'Failed to add biological processes to Neo4j: {e}')
    finally:
        logging.info("Closing Neo4j connection.")
        neo4j_conn.close()
        logging.info("Neo4j connection closed.")


if __name__ == "__main__":
    logging.critical("Initializing script for adding ARUK-UCL biological processes to Neo4j.")
    add_arukucl_to_neo4j_db()