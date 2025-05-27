import os
import sys
from lxml import etree
import logging
import uuid

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from src_pub.utils.logging_config import setup_logging
from src_pub.utils.conn_neo4j import Neo4jConnection
from src_pub.utils.uuid_util import generate_uuid

class DrugBank2Neo4j:
    def __init__(self, input_file_path, namespace):
        """
        Initialize the DrugBank2Neo4j class.

        Args:
            input_file_path (str): The path to the DrugBank XML file.
            namespace (dict): The namespace dictionary for parsing the XML.
        """
        self.input_file_path = input_file_path
        self.namespace = namespace
        setup_logging(log_file_prefix="logs/drugbank_pipeline", processed_file="drugbank_full_dataset")

    def extract_drug_info(self, drug_elem):
        """
        Extracts drug information from an XML element.

        Args:
            drug_elem (etree.Element): The XML element representing a drug.

        Returns:
            dict: A dictionary containing extracted drug information.
        """
        def get_text(element, default=''):
            return element.text if element is not None else default

        go_classifiers_info = []
        for go in drug_elem.findall('.//{http://www.drugbank.ca}go-classifier'):
            go_classifiers_info.append({
                'Category': get_text(go.find('db:category', namespaces=self.namespace)),
                'Description': get_text(go.find('db:description', namespaces=self.namespace))
            })

        classification_elem = drug_elem.find('db:classification', namespaces=self.namespace)
        classification_info = {
            'Direct Parent': get_text(classification_elem.find('db:direct-parent', namespaces=self.namespace)),
            'Kingdom': get_text(classification_elem.find('db:kingdom', namespaces=self.namespace)),
            'Superclass': get_text(classification_elem.find('db:superclass', namespaces=self.namespace)),
            'Class': get_text(classification_elem.find('db:class', namespaces=self.namespace)),
        } if classification_elem is not None else {}

        drug_info = {
            'DrugBank ID': get_text(drug_elem.find('db:drugbank-id', namespaces=self.namespace)),
            'Name': get_text(drug_elem.find('db:name', namespaces=self.namespace)),
            'Description': get_text(drug_elem.find('db:description', namespaces=self.namespace)),
            'GO Classifiers': go_classifiers_info,
            'Simple Description': get_text(drug_elem.find('db:simple-description', namespaces=self.namespace)),
            'Clinical Description': get_text(drug_elem.find('db:clinical-description', namespaces=self.namespace)),
            'Therapeutically Significant': get_text(drug_elem.find('db:therapeutically-significant', namespaces=self.namespace)),
            'Affected Organisms': [org.text for org in drug_elem.findall('db:affected-organisms/db:affected-organism', namespaces=self.namespace)],
            'Indication': get_text(drug_elem.find('db:indication', namespaces=self.namespace)),
            'Pharmacodynamics': get_text(drug_elem.find('db:pharmacodynamics', namespaces=self.namespace)),
            'Mechanism of Action': get_text(drug_elem.find('db:mechanism-of-action', namespaces=self.namespace)),
            'Direct Parent': classification_info.get('Direct Parent', ''),
            'Kingdom': classification_info.get('Kingdom', ''),
            'Superclass': classification_info.get('Superclass', ''),
            'Class': classification_info.get('Class', ''),
        }
        return drug_info

    def parse_drugbank_xml(self):
        """
        Parses the DrugBank XML file and extracts drug information.

        Returns:
            list: A list of dictionaries, each containing information about a drug.
        """
        try:
            logging.info(f"Starting to parse the XML file: {self.input_file_path}")
            context = etree.iterparse(self.input_file_path, events=('end',), tag='{http://www.drugbank.ca}drug')
            logging.info(f"XML file parsed successfully.")

            count = 0
            drug_details = []

            for event, elem in context:
                try:
                    if elem.find('db:drugbank-id', namespaces=self.namespace) is not None:
                        drug_info = self.extract_drug_info(elem)
                        drug_details.append(drug_info)
                        count += 1
                        if count % 5 == 0:
                            logging.info(f"Processed {count} drugs: {drug_info}")

                    # Clear processed element from memory
                    elem.clear()
                    while elem.getprevious() is not None:
                        del elem.getparent()[0]

                except Exception as e:
                    logging.error(f"Error processing drug element: {e}")

            logging.info(f"Total drugs processed: {count}")
            return drug_details

        except Exception as e:
            logging.error(f"Failed to parse the XML file: {e}")
            raise

    def add_drug_to_neo4j(self, tx, drug):
        """
        Adds drug information to the Neo4j database.

        Args:
            tx (neo4j.Transaction): The Neo4j transaction object.
            drug (dict): A dictionary containing drug information to be added to the database.
        """
        go_descriptions = drug.get('GO Classifiers', [])
        go_terms = [term for desc in go_descriptions for term in desc['Description'].split('; ')]

        drug_properties = {
            'uuid': generate_uuid(),  # Generate a UUID for each drug
            'drugbankId': drug.get('DrugBank ID', ''),
            'name': drug.get('Name', ''),
            'description': drug.get('Description', ''),
            'simpleDescription': drug.get('Simple Description', ''),
            'clinicalDescription': drug.get('Clinical Description', ''),
            'therapeuticallySignificant': drug.get('Therapeutically Significant', ''),
            'indication': drug.get('Indication', ''),
            'pharmacodynamics': drug.get('Pharmacodynamics', ''),
            'mechanismOfAction': drug.get('Mechanism of Action', ''),
            'affectedGoProcess': go_terms,
            'directParent': drug.get('Direct Parent', ''),
            'kingdom': drug.get('Kingdom', ''),
            'superclass': drug.get('Superclass', ''),
            'class': drug.get('Class', ''),
        }

        logging.info(f"Adding drug to Neo4j with properties: {drug_properties}")

        result = tx.run("""
            MERGE (d:Drug {drugbankId: $drugbankId})
            ON CREATE SET
                d.uuid = $uuid,
                d.name = $name,
                d.description = $description,
                d.simpleDescription = $simpleDescription,
                d.clinicalDescription = $clinicalDescription,
                d.therapeuticallySignificant = $therapeuticallySignificant,
                d.indication = $indication,
                d.pharmacodynamics = $pharmacodynamics,
                d.mechanismOfAction = $mechanismOfAction,
                d.affectedGoProcess = $affectedGoProcess,
                d.directParent = $directParent,
                d.kingdom = $kingdom,
                d.superclass = $superclass,
                d.class = $class
        """, **drug_properties)

        counters = result.consume().counters
        logging.debug(f"Result from Neo4j: nodes created: {counters.nodes_created}, relationships created: {counters.relationships_created}, properties set: {counters.properties_set}")

    def run_pipeline(self):
        """
        Main function to parse DrugBank XML and add drug information to Neo4j.
        """
        try:
            # Parse the entire DrugBank XML file
            drug_details = self.parse_drugbank_xml()

            # Add drugs to the Neo4j database
            with Neo4jConnection(os.getenv("uri"), os.getenv("username"), os.getenv("password")) as conn:
                logging.info(f"Starting to add drugs to the Neo4j database.")
                with conn.driver.session() as session:
                    for drug in drug_details:
                        session.execute_write(self.add_drug_to_neo4j, drug)
                logging.info(f"Data has been added to the Neo4j database.")

            print("Data has been added to the Neo4j database")

        except Exception as e:
            logging.error(f"An error occurred: {e}")
            raise


if __name__ == "__main__":
    logging.critical("Initializing script for adding drugbank entities to Neo4j.")
    input_file_path = 'drugbank_full_dataset.xml' # Update this path to the location of the DrugBank XML file on your system
    namespace = {'db': 'http://www.drugbank.ca'}
    pipeline = DrugBank2Neo4j(input_file_path, namespace)
    pipeline.run_pipeline()

