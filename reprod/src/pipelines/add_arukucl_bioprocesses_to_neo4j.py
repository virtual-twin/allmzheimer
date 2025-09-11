# file: src/pipelines/add_arukucl_bioprocesses_to_neo4j.py

import os
import sys
import logging
import pandas as pd
from dotenv import load_dotenv

# Ensure package imports work when run as a module
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.logging_config import setup_logging
from src.utils.conn_neo4j import Neo4jConnection    
from src.utils.uuid_util import generate_uuid       


def setup_environment():
    """Load .env, configure logging, and validate configuration."""
    load_dotenv()
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )
    # Resolve paths and connection info
    tsv = os.getenv(
        "BIOPROCESS_ARUK_UCL_GO_TERMS_TSV",
        "/app/datasets/bioprocess_ARUK-UCL-GO-terms.tsv",
    )
    uri = os.getenv("uri")
    user = os.getenv("username")
    pwd = os.getenv("password")

    missing = []
    if not uri: missing.append("uri")
    if not user: missing.append("username")
    if not pwd: missing.append("password")

    if missing:
        logging.critical("Missing Neo4j env vars: %s", ", ".join(missing))
        sys.exit(2)

    logging.info("Config:")
    logging.info("  TSV: %s", tsv)
    logging.info("  Neo4j URI: %s", uri)
    logging.info("  Neo4j user: %s", user)
    return tsv, uri, user, pwd


class Neo4jConnectionExtended(Neo4jConnection):
    """Adds biological processes to Neo4j."""

    def ensure_constraints(self):
        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    "CREATE CONSTRAINT biologicalprocess_goTerm IF NOT EXISTS "
                    "FOR (b:BiologicalProcess) REQUIRE b.goTerm IS UNIQUE"
                )
            )
            logging.info("Constraint ensured: biologicalprocess_goTerm(goTerm UNIQUE)")

    def add_biological_process(self, data: pd.DataFrame):
        """Row-by-row MERGE; records created vs. merged via summary counters."""
        if data.empty:
            logging.warning("Input dataframe is empty; nothing to import.")
            return

        required_cols = {"GO TERM", "GO NAME"}
        missing = required_cols - set(data.columns)
        if missing:
            logging.critical("Missing required columns: %s", ", ".join(sorted(missing)))
            sys.exit(3)

        created_cnt, matched_cnt = 0, 0

        def upsert_row(tx, row_dict):
            # Property mapping
            property_mapping = {
                'GENE PRODUCT DB': 'geneProductDb',
                'GENE PRODUCT ID': 'geneProductId',
                'SYMBOL': 'symbol',
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
            attrs = {}
            for col, neo_prop in property_mapping.items():
                if col in row_dict and pd.notna(row_dict[col]):
                    attrs[neo_prop] = str(row_dict[col])

            # Label mirrors goName; UUID per import attempt
            if 'GO NAME' in row_dict and pd.notna(row_dict['GO NAME']):
                attrs['label'] = str(row_dict['GO NAME'])
            attrs['uuid'] = generate_uuid()

            # MERGE on goTerm; accumulate selected props if already present
            query = (
                "MERGE (b:BiologicalProcess {goTerm: $goTerm}) "
                "ON CREATE SET b += $attributes "
                "ON MATCH SET "
                "b.symbol = CASE WHEN b.symbol IS NULL THEN $attributes.symbol "
                "               WHEN $attributes.symbol IS NULL THEN b.symbol "
                "               ELSE b.symbol + ', ' + $attributes.symbol END, "
                "b.geneProductDb = CASE WHEN b.geneProductDb IS NULL THEN $attributes.geneProductDb "
                "                       WHEN $attributes.geneProductDb IS NULL THEN b.geneProductDb "
                "                       ELSE b.geneProductDb + ', ' + $attributes.geneProductDb END, "
                "b.geneProductId = CASE WHEN b.geneProductId IS NULL THEN $attributes.geneProductId "
                "                       WHEN $attributes.geneProductId IS NULL THEN b.geneProductId "
                "                       ELSE b.geneProductId + ', ' + $attributes.geneProductId END, "
                "b.qualifier = CASE WHEN b.qualifier IS NULL THEN $attributes.qualifier "
                "                  WHEN $attributes.qualifier IS NULL THEN b.qualifier "
                "                  ELSE b.qualifier + ', ' + $attributes.qualifier END, "
                "b.ecoId = CASE WHEN b.ecoId IS NULL THEN $attributes.ecoId "
                "              WHEN $attributes.ecoId IS NULL THEN b.ecoId "
                "              ELSE b.ecoId + ', ' + $attributes.ecoId END, "
                "b.goEvidenceCode = CASE WHEN b.goEvidenceCode IS NULL THEN $attributes.goEvidenceCode "
                "                        WHEN $attributes.goEvidenceCode IS NULL THEN b.goEvidenceCode "
                "                        ELSE b.goEvidenceCode + ', ' + $attributes.goEvidenceCode END, "
                "b.reference = CASE WHEN b.reference IS NULL THEN $attributes.reference "
                "                  WHEN $attributes.reference IS NULL THEN b.reference "
                "                  ELSE b.reference + ', ' + $attributes.reference END, "
                "b.withFrom = CASE WHEN b.withFrom IS NULL THEN $attributes.withFrom "
                "                 WHEN $attributes.withFrom IS NULL THEN b.withFrom "
                "                 ELSE b.withFrom + ', ' + $attributes.withFrom END, "
                "b.taxonId = CASE WHEN b.taxonId IS NULL THEN $attributes.taxonId "
                "                WHEN $attributes.taxonId IS NULL THEN b.taxonId "
                "                ELSE b.taxonId + ', ' + $attributes.taxonId END, "
                "b.assignedBy = CASE WHEN b.assignedBy IS NULL THEN $attributes.assignedBy "
                "                   WHEN $attributes.assignedBy IS NULL THEN b.assignedBy "
                "                   ELSE b.assignedBy + ', ' + $attributes.assignedBy END, "
                "b.annotationExtension = CASE WHEN b.annotationExtension IS NULL THEN $attributes.annotationExtension "
                "                             WHEN $attributes.annotationExtension IS NULL THEN b.annotationExtension "
                "                             ELSE b.annotationExtension + ', ' + $attributes.annotationExtension END, "
                "b.goAspect = CASE WHEN b.goAspect IS NULL THEN $attributes.goAspect "
                "                 WHEN $attributes.goAspect IS NULL THEN b.goAspect "
                "                 ELSE b.goAspect + ', ' + $attributes.goAspect END "
                "RETURN b"
            )
            res = tx.run(query, goTerm=row_dict['GO TERM'], attributes=attrs)
            summary = res.consume()
            return summary.counters.nodes_created > 0

        with self.driver.session() as session:
            for idx, row in data.iterrows():
                try:
                    created = session.execute_write(upsert_row, row.to_dict())
                    if created:
                        created_cnt += 1
                    else:
                        matched_cnt += 1
                except Exception as e:
                    logging.error("Row %s failed (%s)", idx, e)

        logging.info("Import complete. Created: %d, Matched: %d", created_cnt, matched_cnt)


def add_arukucl_to_neo4j_db():
    tsv_path, uri, user, pwd = setup_environment()
    setup_logging()

    # Load filtered TSV
    try:
        df = pd.read_csv(tsv_path, sep="\t", dtype=str)
    except Exception as e:
        logging.critical("Failed to load TSV: %s (%s)", tsv_path, e)
        sys.exit(4)

    # Connect + ensure constraint + import
    try:
        neo = Neo4jConnectionExtended(uri=uri, user=user, password=pwd)
    except Exception as e:
        logging.critical("Neo4j connection failed: %s", e)
        sys.exit(5)

    try:
        neo.ensure_constraints()
        neo.add_biological_process(df)
    finally:
        neo.close()


if __name__ == "__main__":
    logging.critical("Initializing ARUK-UCL → Neo4j import.")
    add_arukucl_to_neo4j_db()