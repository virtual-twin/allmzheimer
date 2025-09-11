# file: src/pipelines/connect_bioprocess_with_drug.py
"""
Connect Drug nodes to BiologicalProcess nodes by matching GO IDs.

Logic:
- Read all :Drug nodes with non-empty d.affectedGoProcessId (list of GO IDs as strings).
- Trim/normalise the GO IDs per drug.
- In batched Cypher, for each (drugbankId, goId):
    MATCH (d:Drug {drugbankId})
    MATCH (b:BiologicalProcess {goTerm: goId})
    MERGE (d)-[:AFFECTS]->(b)
- Idempotent by design (MERGE), relies on existing uniqueness constraints:
    - :Drug(drugbankId) UNIQUE
    - :BiologicalProcess(goTerm) UNIQUE
"""

import os
import sys
import logging
from typing import List, Dict, Tuple
from dotenv import load_dotenv


project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.logging_config import setup_logging
from src.utils.conn_neo4j import Neo4jConnection

BATCH_WRITE_SIZE = int(os.getenv("BATCH_WRITE_SIZE", "1000"))


def _resolve_creds() -> Tuple[str, str, str]:
    load_dotenv()
    uri = os.getenv("uri", "bolt://neo4j:7687")
    user = os.getenv("username", "neo4j")
    pwd  = os.getenv("password")
    neo_auth = os.getenv("NEO4J_AUTH", "")
    if not pwd and neo_auth.startswith("neo4j/"):
        pwd = neo_auth[len("neo4j/"):]
    if not pwd:
        raise RuntimeError("Neo4j password not provided via 'password' or NEO4J_AUTH.")
    return uri, user, pwd


def _collect_drug_goids(conn: Neo4jConnection) -> List[Dict[str, object]]:
    """
    Return [{'drugbankId': str, 'goIds': [str, ...]}, ...] for Drugs with affectedGoProcessId.
    """
    query = (
        "MATCH (d:Drug) "
        "WHERE d.affectedGoProcessId IS NOT NULL AND size(d.affectedGoProcessId) > 0 "
        "RETURN d.drugbankId AS drugbankId, d.affectedGoProcessId AS ids"
    )
    rows: List[Dict[str, object]] = []
    with conn.driver.session() as session:
        for rec in session.run(query):
            dbid = rec["drugbankId"]
            raw = rec["ids"]
            if isinstance(raw, list):
                seen = set()
                cleaned = []
                for x in raw:
                    if not isinstance(x, str):
                        continue
                    t = x.strip()
                    if not t or t in seen:
                        continue
                    seen.add(t)
                    cleaned.append(t)
            else:
                cleaned = []
            rows.append({"drugbankId": dbid, "goIds": cleaned})
    logging.info("Collected %d Drug nodes with affectedGoProcessId.", len(rows))
    return rows


def _chunk(lst: List[dict], n: int) -> List[List[dict]]:
    return [lst[i:i+n] for i in range(0, len(lst), n)]


def _write_affects(conn: Neo4jConnection, rows: List[Dict[str, object]]) -> None:
    """
    For each row {drugbankId, goIds}, MERGE (:Drug)-[:AFFECTS]->(:BiologicalProcess {goTerm}).
    Only creates an edge when the BiologicalProcess exists.
    """
    if not rows:
        logging.info("No rows to connect.")
        return

    cypher = (
        "UNWIND $rows AS row "
        "MATCH (d:Drug {drugbankId: row.drugbankId}) "
        "UNWIND row.goIds AS goid "
        "WITH d, trim(goid) AS goid "
        "MATCH (b:BiologicalProcess {goTerm: goid}) "
        "MERGE (d)-[:AFFECTS]->(b)"
    )

    total_rel_created = 0
    with conn.driver.session() as session:
        for batch in _chunk(rows, BATCH_WRITE_SIZE):
            summary = session.run(cypher, rows=batch).consume().counters
            total_rel_created += summary.relationships_created
            logging.info(
                "Processed batch of %d drugs (relationships_created=%d).",
                len(batch), summary.relationships_created
            )

    logging.info("AFFECTS relationships created in total: %d", total_rel_created)


def main() -> None:
    setup_logging()
    uri, user, pwd = _resolve_creds()
    logging.info("Connecting Drug nodes to BiologicalProcess nodes via GO IDs.")

    with Neo4jConnection(uri=uri, user=user, password=pwd) as conn:
        rows = _collect_drug_goids(conn)
        if not rows:
            logging.warning("No Drug nodes with affectedGoProcessId; nothing to connect.")
            return
        _write_affects(conn, rows)

    logging.info("Drug→BiologicalProcess connection step completed.")


if __name__ == "__main__":
    main()