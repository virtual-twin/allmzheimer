import os
import sys
import csv
import logging
from neo4j import GraphDatabase

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from src_pub.utils.conn_neo4j import Neo4jConnection

# Explicit logging configuration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('drugbank_export.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

class Neo4jDrugExporter:
    def __init__(self):
        logging.info("Neo4jDrugExporter initialized")

    def fetch_drugs_from_neo4j(self, exclude_alzheim=False):
        """
        Fetch drug nodes from Neo4j database.

        Args:
            exclude_alzheim (bool): If True, exclude nodes with 'indication' property containing 'alzheim'.

        Returns:
            list: A list of dictionaries, each containing drug properties.
        """
        if exclude_alzheim:
            query = """
            MATCH (d:Drug)
            WHERE NOT toLower(d.indication) CONTAINS 'alzheim' OR d.indication IS NULL OR d.indication = ''
            RETURN d
            """
        else:
            query = """
            MATCH (d:Drug)
            WHERE toLower(d.indication) CONTAINS 'alzheim'
            RETURN d
            """

        try:
            with Neo4jConnection(os.getenv("uri"), os.getenv("username"), os.getenv("password")) as conn:
                with conn.driver.session() as session:
                    result = session.run(query)
                    drugs = [record["d"] for record in result]
                    return drugs
        except Exception as e:
            logging.error(f"An error occurred while fetching drugs from Neo4j: {e}")
            raise

    def export_drugs_to_csv(self, drugs, output_file_path):
        """
        Export drug data to a CSV file.

        Args:
            drugs (list): A list of dictionaries containing drug data.
            output_file_path (str): The path to the output CSV file.
        """
        if not drugs:
            logging.warning("No drug data to export.")
            return

        # Specify the order of columns with "name" first
        keys = ['name', 'description', 'indication', 'affectedGoProcess', 'therapeuticallySignificant', 'pharmacodynamics', 
                'simpleDescription', 'clinicalDescription', 
                'mechanismOfAction', 'affectedGoProcessId', 'drugbankId']
        
        # Adding any additional keys that are present in the data but not in the specified order
        additional_keys = set(drugs[0].keys()) - set(keys)
        keys.extend(additional_keys)

        try:
            with open(output_file_path, 'w', newline='') as output_file:
                dict_writer = csv.DictWriter(output_file, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(drugs)
                logging.info(f"Drug data exported successfully to {output_file_path}")
        except Exception as e:
            logging.error(f"An error occurred while writing to CSV: {e}")
            raise

    def run_export_pipeline(self, output_file_path, exclude_alzheim=False):
        """
        Main function to fetch drug data from Neo4j and export it to a CSV file.

        Args:
            output_file_path (str): The path to the output CSV file.
            exclude_alzheim (bool): If True, exclude nodes with 'indication' property containing 'alzheim'.
        """
        try:
            logging.info("Starting to fetch drugs from the Neo4j database.")
            drugs = self.fetch_drugs_from_neo4j(exclude_alzheim=exclude_alzheim)
            logging.info(f"Fetched {len(drugs)} drugs from the Neo4j database.")
            self.export_drugs_to_csv(drugs, output_file_path)
        except Exception as e:
            logging.error(f"An error occurred during the export pipeline: {e}")
            raise

if __name__ == "__main__":
    logging.critical("Initializing script for exporting drugbank entities from Neo4j to CSV.")

    # Exporting nodes containing 'alzheim'
    output_file_path_inclusive = 'drugbank_drugs_alzheimers.csv'
    exporter_inclusive = Neo4jDrugExporter()
    exporter_inclusive.run_export_pipeline(output_file_path_inclusive, exclude_alzheim=False)

    # Exporting nodes excluding 'alzheim'
    output_file_path_exclusive = '/datasets/drugbank_drugs_non_alzheimers.csv'
    exporter_exclusive = Neo4jDrugExporter()
    exporter_exclusive.run_export_pipeline(output_file_path_exclusive, exclude_alzheim=True)
