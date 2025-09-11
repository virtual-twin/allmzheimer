# file: tests/verify_ad_drug_and_bioprocess_counts.py
"""
Verification of post-connection counts:

1) AD-related drugs:
   Count distinct :Drug with at least one path
   (:Drug)-[:AFFECTS]->(:BiologicalProcess)-[:RELATED_TO]->(:Pathology {pathologyName:'Alzheimer'})
   Reference: EXACTLY 5,967.

   Policy:
   - Exactly 5,967 -> INFO (matches reference).
   - 5,600–6,200   -> WARNING (minor deviation; likely mapping/version drift).
   - < 5,600 or > 6,200 -> ERROR (large deviation; likely mapping/import issue).

2) Biological processes:
   Count of :BiologicalProcess nodes.
   Reference: EXACTLY 1,778.

   Policy:
   - Exactly 1,778 -> INFO (matches ARUK-UCL filtered set).
   - 1,700–1,850   -> WARNING (unexpected; ARUK-UCL is stable—investigate).
   - < 1,700 or > 1,850 -> ERROR (strongly suggests import/filtering defect).

Exit code:
- 0 for INFO/WARNING only,
- 1 for any ERROR or connectivity/query failure.
"""

import os
import sys
import logging
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Make project imports available
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.logging_config import setup_logging  # type: ignore

# Reference values and thresholds
AD_REF = 5967
AD_WARN_LOW, AD_WARN_HIGH = 5600, 6200

BP_REF = 1778
BP_WARN_LOW, BP_WARN_HIGH = 1700, 1850


def _get_creds():
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


def main() -> int:
    setup_logging()
    logger = logging.getLogger("verify.postconnect")

    try:
        uri, user, pwd = _get_creds()
        driver = GraphDatabase.driver(uri, auth=(user, pwd))
        driver.verify_connectivity()
    except Exception as e:
        logging.critical("Connectivity failed: %s", e)
        return 1

    try:
        with driver.session() as session:
            # 1) Distinct drugs linked to AD-related biological processes
            ad_res = session.run("""
                MATCH (d:Drug)-[:AFFECTS]->(:BiologicalProcess)-[:RELATED_TO]->(:Pathology {pathologyName:'Alzheimer'})
                RETURN count(distinct d) AS ad_drugs
            """).single()
            # 2) Biological process count
            bp_res = session.run("""
                MATCH (b:BiologicalProcess)
                RETURN count(b) AS bio_count
            """).single()

        if ad_res is None or bp_res is None:
            logging.critical("Verification queries returned no results. Aborting.")
            return 1

        ad_count = int(ad_res["ad_drugs"])
        bp_count = int(bp_res["bio_count"])

    except Exception as e:
        logging.critical("Verification queries failed: %s", e)
        return 1
    finally:
        driver.close()

    # --- Evaluate biological processes first (dataset stability is expected) ---
    exit_code = 0
    if bp_count == BP_REF:
        logging.info(
            "Observed exactly %d BiologicalProcess nodes, matching the ARUK-UCL filtered reference.",
            bp_count,
        )
    elif BP_WARN_LOW <= bp_count <= BP_WARN_HIGH:
        logging.warning(
            "Observed %d BiologicalProcess nodes (expected 1,778). "
            "ARUK-UCL export is not expected to drift; please investigate this deviation carefully.",
            bp_count,
        )
    else:
        logging.error(
            "Observed %d BiologicalProcess nodes (outside [%d, %d]). "
            "This strongly suggests an import/filtering defect in the ARUK-UCL processing.",
            bp_count, BP_WARN_LOW, BP_WARN_HIGH,
        )
        exit_code = 1  # escalate to failure for large deviation

    # --- Evaluate AD-related drug count ---
    if ad_count == AD_REF:
        logging.info(
            "Observed exactly %d distinct Drug nodes related to AD processes (via AFFECTS→RELATED_TO path).",
            ad_count,
        )
    elif AD_WARN_LOW <= ad_count <= AD_WARN_HIGH:
        logging.warning(
            "Observed %d distinct AD-related drugs (expected 5,967). "
            "This minor deviation may reflect GO mapping or dataset/version differences. Since the QuickGo API may change its output slightly, this is expected as long as it is within the expected range.",
            ad_count,
        )
    else:
        logging.error(
            "Observed %d distinct AD-related drugs (outside [%d, %d]). "
            "This large deviation likely indicates a mapping or relationship creation defect.",
            ad_count, AD_WARN_LOW, AD_WARN_HIGH,
        )
        exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())