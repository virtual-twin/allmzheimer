# file: tests/verify_number_of_drugs.py
"""
Verify the number of unique DrugBank drugs present in the Neo4j graph.

Reference point:
- DrugBank 5.1.12 (released 2024-03-14) contained EXACTLY 16,581 unique drugs.

Policy:
- Exactly 16,581  -> INFO: matches expected (v5.1.12).
- 16,000–16,580   -> WARNING: below reference; likely different DB version; log discrepancy.
- 16,582–24,999   -> WARNING: above reference; likely different DB version; log discrepancy.
- < 16,000        -> ERROR: likely dataset or import issue.
- ≥ 25,000        -> ERROR: large deviation; either major DB change or data quality issue.

Additionally:
- If the count of :Drug nodes differs from count(distinct d.drugbankId),
  log ERROR because the uniqueness expectation is violated.

Exit code:
- 0 for INFO/WARNING
- 1 for ERROR or connection failures
"""

import os
import sys
import logging
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Ensure project root is importable (so we can use logging_config)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.logging_config import setup_logging  # type: ignore


REFERENCE_COUNT = 16581  # DrugBank v5.1.12 (2024-03-14)
LOWER_BOUND = 16000
UPPER_BOUND = 25000


def _get_creds():
    load_dotenv()
    uri = os.getenv("uri", "bolt://neo4j:7687")
    user = os.getenv("username", "neo4j")
    pwd = os.getenv("password")
    if not pwd and os.getenv("NEO4J_AUTH", "").startswith("neo4j/"):
        pwd = os.getenv("NEO4J_AUTH")[len("neo4j/"):]
    if not pwd:
        raise RuntimeError("Neo4j password not provided via 'password' or NEO4J_AUTH.")
    return uri, user, pwd


def main() -> int:
    setup_logging()  # honours LOG_LEVEL or defaults to INFO
    logger = logging.getLogger("drugcount.verify")

    try:
        uri, user, pwd = _get_creds()
    except Exception as e:
        logging.critical("Failed to resolve Neo4j credentials: %s", e)
        return 1

    try:
        driver = GraphDatabase.driver(uri, auth=(user, pwd))
        driver.verify_connectivity()
    except Exception as e:
        logging.critical("Neo4j connectivity failed (%s): %s", uri, e)
        return 1

    try:
        with driver.session() as session:
            rec = session.run(
                """
                MATCH (d:Drug)
                RETURN count(d) AS total_nodes,
                       count(distinct d.drugbankId) AS unique_ids
                """
            ).single()
            total_nodes = int(rec["total_nodes"])
            unique_ids = int(rec["unique_ids"])
    except Exception as e:
        logging.critical("Cypher query failed: %s", e)
        driver.close()
        return 1
    finally:
        driver.close()

    # Sanity: uniqueness expectation
    if total_nodes != unique_ids:
        logging.error(
            "Uniqueness violation detected: total :Drug nodes (%d) != distinct drugbankId (%d). "
            "This suggests missing or bypassed uniqueness constraints on :Drug(drugbankId), "
            "or non-canonical node creation.",
            total_nodes, unique_ids,
        )
        # Still proceed to threshold analysis; keep exit 1 at end.

    # Threshold analysis
    delta = unique_ids - REFERENCE_COUNT
    if unique_ids == REFERENCE_COUNT:
        logging.info(
            "Observed exactly %d unique DrugBank drugs, matching DrugBank v5.1.12 (released 2024-03-14). "
            "Downstream analyses should reproduce previously published counts within expected tolerance.",
            unique_ids,
        )
        # If uniqueness violated above, treat as error
        return 1 if total_nodes != unique_ids else 0

    if LOWER_BOUND <= unique_ids < REFERENCE_COUNT:
        logging.warning(
            "Observed %d unique DrugBank drugs (Δ = %d vs. 16,581). "
            "This is slightly below the DrugBank v5.1.12 reference and is most consistent with "
            "a different DrugBank release or a dataset subset. Minor deviations in downstream "
            "results are possible.",
            unique_ids, delta,
        )
        return 1 if total_nodes != unique_ids else 0

    if REFERENCE_COUNT < unique_ids < UPPER_BOUND:
        logging.warning(
            "Observed %d unique DrugBank drugs (Δ = +%d vs. 16,581). "
            "This exceeds the v5.1.12 reference and likely reflects a different DrugBank release. "
            "Minor deviations in downstream results are possible.",
            unique_ids, delta,
        )
        return 1 if total_nodes != unique_ids else 0

    if unique_ids < LOWER_BOUND:
        logging.error(
            "Observed %d unique DrugBank drugs (< %d). "
            "This is substantially lower than expected for current DrugBank releases and strongly "
            "suggests a dataset or import defect (e.g., truncated XML, failed parsing, or filtering).",
            unique_ids, LOWER_BOUND,
        )
        return 1

    if unique_ids >= UPPER_BOUND:
        logging.error(
            "Observed %d unique DrugBank drugs (≥ %d). "
            "This markedly exceeds expectations and implies either a major change in DrugBank's scope "
            "or a data quality problem (e.g., non-primary IDs treated as unique). Please audit the import.",
            unique_ids, UPPER_BOUND,
        )
        return 1

    # Fallback (should be unreachable)
    logging.error("Unexpected state encountered with unique count = %d.", unique_ids)
    return 1


if __name__ == "__main__":
    sys.exit(main())