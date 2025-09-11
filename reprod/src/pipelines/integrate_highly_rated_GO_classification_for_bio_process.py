import os
import sys
import json
import logging
from typing import List, Optional, Dict, Any

from neo4j import GraphDatabase
from dotenv import load_dotenv


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


try:
    from src.utils.logging_config import setup_logging
    _use_custom_logging = True
except Exception:
    _use_custom_logging = False

load_dotenv()

logger = logging.getLogger(__name__)

# ------------- helpers -------------
def _init_logging() -> None:
    if _use_custom_logging:
        setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
    else:
        logging.basicConfig(
            level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s | %(message)s",
        )

def _split_dirs(raw: str) -> List[str]:
    out: List[str] = []
    if not raw:
        return out
    for chunk in raw.split(","):
        out.extend(x.strip() for x in chunk.split(":") if x.strip())
    return out

def _extract_drugbank_id_from_filename(filename: str) -> str:
    """
    Accept filenames like:
      response_DB00022.json -> DB00022
      DB00022.json          -> DB00022 (fallback)
    """
    base = os.path.basename(filename)
    if base.startswith("response_"):
        base = base[len("response_"):]
    if base.endswith(".json"):
        base = base[:-5]
    return base

def _parse_classification(payload: Dict[str, Any]) -> Optional[str]:
    """
    Given the loaded JSON payload from a response file, extract the classification string.

    Expected primary shape:
      { "response": "{ \"Drug_Classification\": \"<GO term>\" }" }

    Also supports:
      { "response": { "Drug_Classification": "<GO term>" } }
    """
    if not isinstance(payload, dict):
        return None

    resp = payload.get("response")
    # Case A: response is already a dict
    if isinstance(resp, dict):
        return resp.get("Drug_Classification")

    # Case B: response is a string containing JSON
    if isinstance(resp, str):
        resp_str = resp.strip()
        # Some models might wrap the dict in quotes or add stray backticks; try to clean minimally
        # Attempt to load once
        try:
            obj = json.loads(resp_str)
            if isinstance(obj, dict):
                return obj.get("Drug_Classification")
        except Exception:
            # As a fallback, try to strip common fences
            cleaned = resp_str.strip("` \n\t")
            try:
                obj2 = json.loads(cleaned)
                if isinstance(obj2, dict):
                    return obj2.get("Drug_Classification")
            except Exception:
                return None

    # If response field not present or unexpected
    return None

def _update_drug_node(session, drugbank_id: str, classification: str, index: int) -> bool:
    """
    Update Drug node with property go_classification_<index> = classification.
    """
    prop = f"go_classification_{index}"
    try:
        result = session.run(
            f"""
            MATCH (d:Drug {{drugbankId: $drugbank_id}})
            SET d.{prop} = $classification
            RETURN d.drugbankId AS id
            """,
            drugbank_id=drugbank_id,
            classification=classification,
        )
        rec = result.single()
        if rec and rec.get("id"):
            logger.info("Set %s for %s → %r", prop, drugbank_id, classification)
            return True
        logger.warning("No Drug node matched for drugbankId=%s", drugbank_id)
        return False
    except Exception as e:
        logger.error("Neo4j update failed for %s: %s", drugbank_id, e)
        return False

def _resolve_input_dirs() -> List[str]:
    """
    Priority:
      1) GO_CLASSIFICATION_RESPONSES_DIRS (comma/colon separated)
      2) GO_CLASSIFICATION_RESPONSES_DIR (single)
      3) default /app/exports/GO_classification_responses
    Returns only existing directories; logs warnings for missing.
    """
    multi = os.getenv("GO_CLASSIFICATION_RESPONSES_DIRS", "").strip()
    single = os.getenv("GO_CLASSIFICATION_RESPONSES_DIR", "").strip()

    dirs = _split_dirs(multi) if multi else []
    if not dirs:
        if single:
            dirs = [single]
        else:
            dirs = ["/app/exports/GO_classification_responses"]

    resolved: List[str] = []
    for d in dirs:
        if os.path.isdir(d):
            resolved.append(d)
        else:
            logger.warning("Configured classification directory not found: %s", d)
    return resolved

# ------------- main work -------------
def process_json_files(directories: List[str], uri: str, user: str, password: str) -> int:
    if not directories:
        logger.critical("No valid GO classification response directories to process.")
        return 2

    updated = 0
    total_files = 0
    parse_fail = 0
    not_found = 0

    driver = None
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info("Connected to Neo4j.")

        for index, directory in enumerate(directories):
            files = [f for f in os.listdir(directory) if f.endswith(".json")]
            files.sort()
            logger.info("Dir %d/%d: %s → %d files", index + 1, len(directories), directory, len(files))
            total_files += len(files)

            for fname in files:
                fpath = os.path.join(directory, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        payload = json.load(f)
                except Exception as e:
                    logger.error("Failed reading %s: %s", fpath, e)
                    parse_fail += 1
                    continue

                classification = _parse_classification(payload)
                if not classification:
                    logger.error("No valid 'Drug_Classification' in %s", fpath)
                    parse_fail += 1
                    continue

                drugbank_id = _extract_drugbank_id_from_filename(fname)
                if not drugbank_id:
                    logger.error("Could not infer drugbankId from filename: %s", fname)
                    parse_fail += 1
                    continue

                with driver.session() as session:
                    ok = _update_drug_node(session, drugbank_id, classification, index)
                    if ok:
                        updated += 1
                    else:
                        not_found += 1

    except Exception as e:
        logger.critical("Failed processing GO classification outputs: %s", e)
        return 3
    finally:
        if driver is not None:
            driver.close()

        logger.info("Files scanned: %d", total_files)
        logger.info("Successful updates: %d", updated)
        logger.info("Missing Drug nodes: %d", not_found)
        logger.info("Parse/other failures: %d", parse_fail)

    # Non-zero if nothing updated (helps detect misconfig)
    return 0 if updated > 0 else 4


def main() -> int:
    _init_logging()
    logger.critical("=== Step 29 START: Integrate GO classifications into Neo4j ===")

    uri = os.getenv("uri")
    user = os.getenv("username")
    password = os.getenv("password")

    if not uri or not user:
        logger.critical("Neo4j credentials not set (env: uri, username, password).")
        return 5

    dirs = _resolve_input_dirs()
    for i, d in enumerate(dirs, 1):
        logger.info("  %2d) %s", i, d)

    rc = process_json_files(dirs, uri, user, password)

    if rc == 0:
        logger.info("GO classification integration completed successfully.")
    else:
        logger.error("GO classification integration finished with rc=%d.", rc)

    logger.critical("=== Step 29 END ===")
    return rc


if __name__ == "__main__":
    sys.exit(main())