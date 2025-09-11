# file: src/pipelines/add_drugbank2neo4j.py
# This module provides functionality to parse the DrugBank XML and add drug entities to Neo4j.

import os
import sys
import logging
from typing import Dict, Iterable, Tuple, Optional
from lxml import etree


project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.logging_config import setup_logging
from src.utils.conn_neo4j import Neo4jConnection
from src.utils.uuid_util import generate_uuid


class DrugBank2Neo4j:
    def __init__(self, input_file_path: str, namespace: Dict[str, str]) -> None:
        """
        Initialize the DrugBank2Neo4j class.

        Args:
            input_file_path (str): The path to the DrugBank XML file.
            namespace (dict): The namespace dictionary for parsing the XML.
        """
        self.input_file_path = input_file_path
        self.namespace = namespace
        setup_logging()  # non-interactive, honors LOG_LEVEL

    # ----------------------------- parsing ---------------------------------

    def extract_drug_info(self, drug_elem: etree._Element) -> Dict:
        """
        Extracts drug information from an XML element.

        Args:
            drug_elem (etree.Element): The XML element representing a drug.

        Returns:
            dict: A dictionary containing extracted drug information.
        """
        def get_text(element, default: str = '') -> str:
            return element.text if element is not None and element.text is not None else default

        go_classifiers_info = []
        # canonical QName for elements under DrugBank namespace:
        for go in drug_elem.findall('.//db:go-classifier', namespaces=self.namespace):
            go_classifiers_info.append({
                'Category': get_text(go.find('db:category', namespaces=self.namespace)),
                'Description': get_text(go.find('db:description', namespaces=self.namespace)),
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
            'Affected Organisms': [org.text for org in drug_elem.findall('db:affected-organisms/db:affected-organism', namespaces=self.namespace) if org is not None and org.text],
            'Indication': get_text(drug_elem.find('db:indication', namespaces=self.namespace)),
            'Pharmacodynamics': get_text(drug_elem.find('db:pharmacodynamics', namespaces=self.namespace)),
            'Mechanism of Action': get_text(drug_elem.find('db:mechanism-of-action', namespaces=self.namespace)),
            'Direct Parent': classification_info.get('Direct Parent', ''),
            'Kingdom': classification_info.get('Kingdom', ''),
            'Superclass': classification_info.get('Superclass', ''),
            'Class': classification_info.get('Class', ''),
        }
        return drug_info

    def iter_drugs(self) -> Iterable[Dict]:
        """
        Parses the DrugBank XML file lazily and yields drug dictionaries.
        """
        logging.info("Parsing DrugBank XML: %s", self.input_file_path)
        try:
            context = etree.iterparse(
                self.input_file_path,
                events=('end',),
                tag='{http://www.drugbank.ca}drug'
            )
        except Exception as e:
            logging.critical("Failed to open/parse XML: %s", e)
            raise

        count = 0
        for event, elem in context:
            try:
                # Only process entries that have an ID
                id_elem = elem.find('db:drugbank-id', namespaces=self.namespace)
                if id_elem is not None and (id_text := id_elem.text):
                    yield self.extract_drug_info(elem)
                    count += 1
                    if count % 500 == 0:
                        logging.info("Parsed %d drug elements...", count)
            except Exception as e:
                logging.error("Error processing <drug> element: %s", e)
            finally:
                # aggressive memory cleanup
                elem.clear()
                while elem.getprevious() is not None:
                    del elem.getparent()[0]
        logging.info("Finished XML parsing. Total drugs parsed: %d", count)

    # ----------------------------- neo4j -----------------------------------

    @staticmethod
    def _ensure_constraints(conn: Neo4jConnection) -> None:
        with conn.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    "CREATE CONSTRAINT drug_drugbankId IF NOT EXISTS "
                    "FOR (d:Drug) REQUIRE d.drugbankId IS UNIQUE"
                )
            )
        logging.info("Constraint ensured: :Drug(drugbankId UNIQUE)")

    @staticmethod
    def _merge_drug(tx, drug: Dict) -> None:
        """
        Adds drug information to the Neo4j database.

        Args:
            tx (neo4j.Transaction): The Neo4j transaction object.
            drug (dict): A dictionary containing drug information to be added to the database.
        """
        go_descriptions = drug.get('GO Classifiers', [])
        go_terms = []
        for desc in go_descriptions:
            text = desc.get('Description', '')
            if text:
                go_terms.extend(text.split('; '))

        props = {
            'uuid': generate_uuid(),
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

        # MERGE on stable business key (drugbankId)
        query = (
            "MERGE (d:Drug {drugbankId: $drugbankId}) "
            "ON CREATE SET "
            "  d.uuid = $uuid, "
            "  d.name = $name, "
            "  d.description = $description, "
            "  d.simpleDescription = $simpleDescription, "
            "  d.clinicalDescription = $clinicalDescription, "
            "  d.therapeuticallySignificant = $therapeuticallySignificant, "
            "  d.indication = $indication, "
            "  d.pharmacodynamics = $pharmacodynamics, "
            "  d.mechanismOfAction = $mechanismOfAction, "
            "  d.affectedGoProcess = $affectedGoProcess, "
            "  d.directParent = $directParent, "
            "  d.kingdom = $kingdom, "
            "  d.superclass = $superclass, "
            "  d.class = $class "
        )
        tx.run(query, **props)

    def run_pipeline(self, uri: str, user: str, password: str) -> None:
        """
        Main function to parse DrugBank XML and add drug information to Neo4j.
        """
        logging.info("Starting DrugBank → Neo4j pipeline")
        with Neo4jConnection(uri=uri, user=user, password=password) as conn:
            self._ensure_constraints(conn)
            processed = 0
            with conn.driver.session() as session:
                for drug in self.iter_drugs():
                    session.execute_write(self._merge_drug, drug)
                    processed += 1
                    if processed % 500 == 0:
                        logging.info("Upserted %d drugs...", processed)
            logging.info("Completed upserting %d drugs.", processed)


def _resolve_config() -> Tuple[str, Dict[str, str], str, str, str]:
    """
    Resolve configuration from environment variables with deterministic defaults.
    """
    # DrugBank XML path inside container (bind-mounted from host)
    xml_path = os.getenv("DRUGBANK_XML", "/app/datasets/drugbank_full_dataset.xml")
    # Namespace for DrugBank
    ns_uri = os.getenv("DRUGBANK_NS", "http://www.drugbank.ca")
    namespace = {'db': ns_uri}

    # Neo4j connection (exported by entrypoint.sh or compose env_file)
    uri = os.getenv("uri", "bolt://neo4j:7687")
    user = os.getenv("username", "neo4j")
    pwd = os.getenv("password")
    if not pwd and os.getenv("NEO4J_AUTH", "").startswith("neo4j/"):
        pwd = os.getenv("NEO4J_AUTH")[len("neo4j/"):]
    if not pwd:
        raise RuntimeError("Neo4j password not provided via 'password' or NEO4J_AUTH.")

    return xml_path, namespace, uri, user, pwd


if __name__ == "__main__":
    logging.critical("Initializing script for adding drugbank entities to Neo4j.")
    setup_logging()
    xml, ns, uri, user, pwd = _resolve_config()
    pipeline = DrugBank2Neo4j(xml, ns)
    pipeline.run_pipeline(uri=uri, user=user, password=pwd)