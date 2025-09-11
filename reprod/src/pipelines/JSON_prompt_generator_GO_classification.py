# file: src/pipelines/JSON_prompt_generator_GO_classification.py
import os
import sys
import json
import argparse
import logging
from typing import Dict, Any, List, Optional

from neo4j import GraphDatabase
from dotenv import load_dotenv
import tiktoken

# Ensure project root is on path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Project logging
try:
    from src.utils.logging_config import setup_logging  # noqa: F401
    _use_custom_logging = True
except Exception:
    _use_custom_logging = False

# ---------------- Prompts ----------------
intro = """
You are a language model that classifies medical drugs based on the Gene Ontology (GO) process the drug mainly works on.
You will be provided with the name of the drug, a reason describing what biological process is mainly important for its selection for repurposing and a general list of GO processes the drug works on.
However, the repurposing of the drug is not important to you but the main important Gene Ontology Process it works on is.
Based on the data available, you have to provide the most important Gene Ontology term the drug works on.
You have to provide it EXACTLY as it is given in the list of GO terms at the end of the prompt.
It is mandatory that you choose only one of the GO terms for the drug, spell it exactly as provided and provide the classification in a valid JSON format like this:

"{\\n"
'   "Drug_Classification": "your classification here"\\n'
"}"
Do only provide this particular valid json format at any cost and follow the naming of the classifications provided strictly.
"""

outro = """
It is mandatory that you choose only one of the GO terms (as provided in the list but selected based on the reason) for the drug and provide the exactly spelled GO term in a valid JSON format like this:
This is the mandatory form for your JSON output:
"{\\n"
  '   "Drug_Classification": "Mainly important GO-term exactly spelled here"\\n'
"}"
Do only provide this particular valid json format at any cost and follow the naming of the classifications provided strictly.
"""

# ---------------- Helpers ----------------
def calculate_token_length(text: str) -> int:
    try:
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        # Fallback: rough character-based length
        return len(text)


def generate_prompt(drug_info: Dict[str, Any]) -> str:
    """
    Embed the drug info (name, reason, affectedGoProcess list) into the instruction.
    """
    prompt = intro
    prompt += json.dumps(drug_info, indent=2, ensure_ascii=False)
    prompt += "\n\n"
    prompt += outro
    return prompt


def get_all_drug_ids(uri: str, user: str, password: str, logger: logging.Logger) -> List[str]:
    ids: List[str] = []
    driver = None
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            res = session.run("MATCH (d:Drug) RETURN d.drugbankId AS drugbank_id")
            ids = [rec["drugbank_id"] for rec in res if rec.get("drugbank_id")]
        logger.info("Retrieved %d Drug nodes from Neo4j.", len(ids))
    except Exception as e:
        logger.critical("Failed to retrieve drug IDs: %s", e)
    finally:
        if driver:
            driver.close()
    return ids


def fetch_drug_info(uri: str, user: str, password: str, drugbank_id: str, logger: logging.Logger) -> Optional[Dict[str, Any]]:
    """
    Pull minimal properties needed for the prompt:
      - name
      - reason_rating_0 (string with reasoning from first iteration of static prompts)
      - affectedGoProcess (list or string)
    """
    driver = None
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            rec = session.run(
                """
                MATCH (d:Drug {drugbankId: $drugbank_id})
                RETURN d.name AS name,
                       d.reason_rating_0 AS reason_rating_0,
                       d.affectedGoProcess AS affectedGoProcess
                """,
                drugbank_id=drugbank_id,
            ).single()

            if not rec:
                logger.warning("No Drug node found with drugbankId=%s", drugbank_id)
                return None

            info = {
                "drugbankId": drugbank_id,
                "name": rec.get("name") or "Unknown",
                "reason_rating_0": rec.get("reason_rating_0") or "",
                "affectedGoProcess": rec.get("affectedGoProcess") or [],
            }
            # Normalize affectedGoProcess to a list of strings when possible
            agp = info["affectedGoProcess"]
            if isinstance(agp, str):
                # Attempt to split on common delimiters; keep minimal change
                parts = [p.strip() for p in agp.replace(";", ",").split(",") if p.strip()]
                info["affectedGoProcess"] = parts
            elif not isinstance(agp, list):
                info["affectedGoProcess"] = [str(agp)]

            return info

    except Exception as e:
        logger.critical("Failed retrieving info for %s: %s", drugbank_id, e)
        return None
    finally:
        if driver:
            driver.close()


def save_prompt_file(output_dir: str, drugbank_id: str, name: str, prompt: str, logger: logging.Logger) -> bool:
    try:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f"{drugbank_id}.json")
        payload = {
            "drugbankId": drugbank_id,
            "name": name,
            "prompt": prompt,
            "token_length": calculate_token_length(prompt),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        logger.info("Saved GO classification prompt: %s", path)
        return True
    except Exception as e:
        logger.error("Failed writing prompt for %s: %s", drugbank_id, e)
        return False


def main() -> int:
    # ---- CLI args ----
    parser = argparse.ArgumentParser(
        description="Generate GO classification prompts for all Drug nodes."
    )
    parser.add_argument(
        "--output-dir",
        default=os.getenv("GO_CLASSIFICATION_PROMPTS_DIR", "/app/exports/GO_classification_prompts"),
        help="Directory to write GO classification prompt JSON files (default: /app/exports/GO_classification_prompts)",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("LOG_LEVEL", "INFO"),
        help="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    args = parser.parse_args()

    # ---- Logging ----
    if _use_custom_logging:
        setup_logging(level=args.log_level)
    else:
        logging.basicConfig(
            level=getattr(logging, args.log_level.upper(), logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s | %(message)s",
        )
    logger = logging.getLogger(__name__)

    # ---- ENV creds ----
    load_dotenv()
    uri = os.getenv("uri")
    user = os.getenv("username")
    password = os.getenv("password")

    if not all([uri, user, password]):
        logger.critical("Neo4j credentials are missing. Ensure 'uri', 'username', and 'password' are set in .env.")
        return 2

    logger.critical("=== Step 27 START: Generate GO classification prompts ===")
    logger.info("Output directory: %s", args.output_dir)

    # ---- Retrieve IDs and generate prompts ----
    ids = get_all_drug_ids(uri, user, password, logger)
    if not ids:
        logger.critical("No Drug nodes found; nothing to do.")
        logger.critical("=== Step 27 END (no data) ===")
        return 0

    written = 0
    skipped = 0
    for drug_id in ids:
        info = fetch_drug_info(uri, user, password, drug_id, logger)
        if not info:
            skipped += 1
            continue

        prompt = generate_prompt(
            {
                "name": info["name"],
                "drugbankId": info["drugbankId"],
                "reason_rating_0": info.get("reason_rating_0", ""),
                "affectedGoProcess": info.get("affectedGoProcess", []),
            }
        )

        ok = save_prompt_file(args.output_dir, info["drugbankId"], info["name"], prompt, logger)
        if ok:
            written += 1
        else:
            skipped += 1

    logger.info("GO classification prompts written: %d", written)
    logger.info("Total skipped: %d", skipped)
    logger.critical("=== Step 27 END ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())