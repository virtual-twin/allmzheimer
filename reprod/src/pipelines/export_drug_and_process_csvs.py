# file: src/pipelines/export_drug_and_process_csvs.py

# Export subsets of the Neo4j graph to CSVs for inspection:

import os
import sys
import csv
import logging
from typing import List, Dict, Tuple
from dotenv import load_dotenv


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.logging_config import setup_logging
from src.utils.conn_neo4j import Neo4jConnection

EXPORT_DIR = os.getenv("EXPORT_DIR", "/app/exports")


def _resolve_creds() -> Tuple[str, str, str]:
    load_dotenv()
    uri = os.getenv("uri", "bolt://neo4j:7687")
    user = os.getenv("username", "neo4j")
    pwd  = os.getenv("password")
    neo_auth = os.getenv("NEO4J_AUTH", "")
    if not pwd and neo_auth.startswith("neo4j/"):
        pwd = neo_auth[len("neo4j/"):]
    if not pwd:
        raise RuntimeError("Neo4j password not provided via 'password' or NEO4J_AUTH'.")
    return uri, user, pwd


def _node_to_dict(n) -> Dict[str, object]:
    return dict(n)


def _write_csv(rows: List[Dict[str, object]], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not rows:
        logging.warning("No rows to export for %s; writing headerless empty file.", os.path.basename(path))
        # Still create an empty file for discoverability
        open(path, "w", encoding="utf-8").close()
        return

    # Union of keys across all rows to avoid losing sparse props
    all_keys = []
    seen = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                all_keys.append(k)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys)
        writer.writeheader()
        writer.writerows(rows)
    logging.info("Wrote %d rows to %s", len(rows), path)


def _fetch_drugs_including_alzheim(conn: Neo4jConnection) -> List[Dict[str, object]]:
    query = """
    MATCH (d:Drug)
    WHERE d.indication IS NOT NULL
      AND toLower(d.indication) CONTAINS 'alzheim'
    RETURN d
    """
    out: List[Dict[str, object]] = []
    with conn.driver.session() as session:
        for rec in session.run(query):
            out.append(_node_to_dict(rec["d"]))
    logging.info("Fetched %d drugs with indication mentioning 'alzheim'.", len(out))
    return out


def _fetch_drugs_excluding_alzheim(conn: Neo4jConnection) -> List[Dict[str, object]]:
    query = """
    MATCH (d:Drug)
    WHERE d.indication IS NULL
       OR d.indication = ''
       OR NOT toLower(d.indication) CONTAINS 'alzheim'
    RETURN d
    """
    out: List[Dict[str, object]] = []
    with conn.driver.session() as session:
        for rec in session.run(query):
            out.append(_node_to_dict(rec["d"]))
    logging.info("Fetched %d drugs with indication NULL/empty or not mentioning 'alzheim'.", len(out))
    return out


def _fetch_alzheimer_bioprocesses(conn: Neo4jConnection) -> List[Dict[str, object]]:
    query = """
    MATCH (b:BiologicalProcess)-[:RELATED_TO]->(:Pathology {pathologyName:'Alzheimer'})
    RETURN b
    """
    out: List[Dict[str, object]] = []
    with conn.driver.session() as session:
        for rec in session.run(query):
            out.append(_node_to_dict(rec["b"]))
    logging.info("Fetched %d Alzheimer-related BiologicalProcess nodes.", len(out))
    return out


def main() -> int:
    setup_logging()
    uri, user, pwd = _resolve_creds()
    logging.info("Starting CSV export to %s", EXPORT_DIR)

    paths = {
        "alz_drugs": os.path.join(EXPORT_DIR, "drugbank_drugs_alzheimers.csv"),
        "non_alz_drugs": os.path.join(EXPORT_DIR, "drugbank_drugs_non_alzheimers.csv"),
        "alz_bioprocesses": os.path.join(EXPORT_DIR, "alzheimer_biological_processes.csv"),
    }

    with Neo4jConnection(uri, user, pwd) as conn:
        alz_drugs = _fetch_drugs_including_alzheim(conn)
        _write_csv(alz_drugs, paths["alz_drugs"])

        non_alz_drugs = _fetch_drugs_excluding_alzheim(conn)
        _write_csv(non_alz_drugs, paths["non_alz_drugs"])

        alz_bioprocesses = _fetch_alzheimer_bioprocesses(conn)
        _write_csv(alz_bioprocesses, paths["alz_bioprocesses"])

    logging.info("CSV export completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())