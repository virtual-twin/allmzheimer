# file: src/pipelines/remove_island_drugs.py
"""
Remove Drug nodes that have no AFFECTS relationship to any BiologicalProcess.

Behavior:
- Repeatedly delete in batches to avoid memory spikes.
- Aggregate total deletions via query counters.
- After deletion, report remaining unconnected drugs (should be 0) and connected (kept) count.
- Evaluate deletions against reference: EXACTLY 10,614.
  - 10,614 -> INFO
  - 10,000–11,250 -> WARNING (minor drift)
  - <10,000 or >11,250 -> ERROR (likely defect) and exit 1

"""

import os
import sys
import logging
from typing import Tuple
from dotenv import load_dotenv


project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.logging_config import setup_logging
from src.utils.conn_neo4j import Neo4jConnection

# Reference and tolerance
EXPECTED_DELETIONS = 10614
WARN_LOW = 10000
WARN_HIGH = 11250

DELETE_BATCH_SIZE = int(os.getenv("DELETE_BATCH_SIZE", "1000"))


def _resolve_creds() -> Tuple[str, str, str]:
    load_dotenv()
    uri = os.getenv("uri", "bolt://neo4j:7687")
    user = os.getenv("username", "neo4j")
    pwd = os.getenv("password")
    neo_auth = os.getenv("NEO4J_AUTH", "")
    if not pwd and neo_auth.startswith("neo4j/"):
        pwd = neo_auth[len("neo4j/"):]
    if not pwd:
        raise RuntimeError("Neo4j password not provided via 'password' or NEO4J_AUTH'.")
    return uri, user, pwd


def _count_unconnected(session) -> int:
    rec = session.run("""
        MATCH (d:Drug)
        WHERE NOT (d)-[:AFFECTS]->(:BiologicalProcess)
        RETURN count(d) AS c
    """).single()
    return int(rec["c"]) if rec else 0


def _count_connected(session) -> int:
    rec = session.run("""
        MATCH (d:Drug)-[:AFFECTS]->(:BiologicalProcess)
        RETURN count(distinct d) AS c
    """).single()
    return int(rec["c"]) if rec else 0


def _delete_batch(session, limit: int) -> int:
    # Delete up to `limit` unconnected Drug nodes; return number deleted
    rec = session.run("""
        CALL {
          MATCH (d:Drug)
          WHERE NOT (d)-[:AFFECTS]->(:BiologicalProcess)
          WITH d LIMIT $limit
          DETACH DELETE d
          RETURN count(*) AS deleted
        }
        RETURN deleted
    """, limit=limit).single()
    return int(rec["deleted"]) if rec else 0


def main() -> int:
    setup_logging()
    uri, user, pwd = _resolve_creds()

    total_deleted = 0
    with Neo4jConnection(uri, user, pwd) as conn:
        with conn.driver.session() as session:
            pre_unconnected = _count_unconnected(session)
            logging.info("Unconnected Drug nodes before deletion: %d", pre_unconnected)

            # Batch deletion loop
            while True:
                deleted = _delete_batch(session, DELETE_BATCH_SIZE)
                if deleted == 0:
                    break
                total_deleted += deleted
                logging.info("Deleted batch of %d unconnected Drug nodes (cumulative=%d).",
                             deleted, total_deleted)

            post_unconnected = _count_unconnected(session)
            kept_connected = _count_connected(session)

    # Scientific logging of results
    logging.critical("Total Drug nodes removed: %d", total_deleted)
    logging.critical("Remaining unconnected Drug nodes (should be 0): %d", post_unconnected)
    logging.info("Total Drug nodes kept (connected to BiologicalProcess): %d", kept_connected)

    # Evaluate against reference
    exit_code = 0
    if total_deleted == EXPECTED_DELETIONS:
        logging.info(
            "Observed exactly %d deletions, matching the historical reference for island Drug removal.",
            total_deleted
        )
    elif WARN_LOW <= total_deleted <= WARN_HIGH:
        logging.warning(
            "Observed %d deletions (expected %d). This minor deviation may reflect small mapping/version differences.",
            total_deleted, EXPECTED_DELETIONS
        )
    else:
        logging.error(
            "Observed %d deletions (outside [%d, %d]). This large deviation likely indicates a mapping or deletion logic issue.",
            total_deleted, WARN_LOW, WARN_HIGH
        )
        exit_code = 1

    # Final sanity: after deletion there should be no unconnected drugs
    if post_unconnected > 0:
        logging.error(
            "Post-deletion, %d unconnected Drug nodes remain. This should be zero; investigate batching limits or concurrent writes.",
            post_unconnected
        )
        exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())