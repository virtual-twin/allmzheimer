import os
import sys
import json
import logging
from typing import List, Tuple, Optional

from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.logging_config import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# ---- ENV / defaults ----

#   RESPONSES_DIR/zero_shot_prompts/iteration_*
ZERO_SHOT_RATINGS_DIRS_RAW = os.getenv("ZERO_SHOT_RATINGS_DIRS", "").strip()
RESPONSES_BASE_DIR = os.getenv("RESPONSES_DIR", "/app/llm_outputs/zeroshot_outputs")


def _split_dirs(raw: str) -> List[str]:
    if not raw:
        return []
    parts: List[str] = []
    for chunk in raw.split(","):
        parts.extend(chunk.split(":"))
    return [p.strip() for p in parts if p.strip()]


def _default_dirs_from_step20() -> List[str]:
    """
    Default to all iteration subfolders under RESPONSES_DIR/zero_shot_prompts.
    e.g., /app/exports/llm_responses/zero_shot_prompts/iteration_1, iteration_2, ...
    If none exist, also consider the parent folder itself as a last resort.
    """
    zs_root = os.path.join(RESPONSES_BASE_DIR, "zero_shot_prompts")
    if not os.path.isdir(zs_root):
        return []

    # collect iteration_* dirs
    dirs = []
    try:
        for name in sorted(os.listdir(zs_root)):
            if name.startswith("iteration_"):
                p = os.path.join(zs_root, name)
                if os.path.isdir(p):
                    dirs.append(p)
    except Exception:
        pass

    # fallback to the root if no iteration_* present but the dir exists
    if not dirs:
        dirs = [zs_root]
    return dirs


def _extract_drugbank_id_from_filename(filename: str) -> str:
    # expects names like "response_DB00028.json" -> "DB00028"
    base = os.path.basename(filename)
    if base.startswith("response_"):
        base = base[len("response_"):]
    if base.endswith(".json"):
        base = base[:-5]
    return base


def _parse_llm_envelope(raw_text: str) -> Optional[dict]:
    """
    Parse an Ollama / general LLM envelope or direct JSON string into a dict
    that contains {'reason_rating': str, 'rating': <float or numeric>}.

    Handles:
      - envelope with {"raw_response": "..."} or {"parsed": {...}}
      - {"response": "<json string>"} style
      - direct JSON object
      - quoted JSON object (a JSON string that itself contains JSON)
    """
    # First attempt: load outer
    try:
        outer = json.loads(raw_text)
    except Exception:
        # Maybe the raw text itself is the final dict (rare), try strict again
        try:
            final = json.loads(raw_text.strip())
            return final if isinstance(final, dict) else None
        except Exception:
            return None

    # If the outer is already the final dict
    if isinstance(outer, dict):
        payload = None

        # Prefer 'parsed' if present
        if "parsed" in outer and isinstance(outer["parsed"], dict):
            payload = outer["parsed"]

        # Try parsing 'raw_response' as JSON or as a quoted JSON string
        if payload is None and isinstance(outer.get("raw_response"), str):
            try:
                payload = json.loads(outer["raw_response"])
            except Exception:
                payload = None

        # Ollama style: {"response": "<json string>"}
        if isinstance(payload, dict) and isinstance(payload.get("response"), str):
            try:
                final = json.loads(payload["response"])
                return final if isinstance(final, dict) else None
            except Exception:
                return None

        # If payload is already a dict with reason/rating, return it
        if isinstance(payload, dict):
            return payload

        # As a last resort, if outer already looks like the final payload
        return outer if isinstance(outer, dict) else None

    # If the outer is a string (i.e., the entire file was a quoted JSON object)
    if isinstance(outer, str):
        try:
            final = json.loads(outer)
            return final if isinstance(final, dict) else None
        except Exception:
            return None

    return None

def update_drug_node(session, drugbank_id: str, response_json: dict, token_length: int, index: int) -> bool:
    """
    Update a Drug node with zero-shot rating fields for a given iteration index.
    Returns True if the update matched a node, False otherwise (e.g., drug not in DB).
    """
    try:
        logger.debug(f"response_json type: {type(response_json)}")
        logger.debug(f"response_json content: {response_json}")

        if isinstance(response_json, str):
            logger.error("response_json is still a string, skipping update.")
            return False
        
        reason_rating = response_json.get('reason_rating', '')

        # robust float coercion
        rating_val = response_json.get('rating', 0.0)
        try:
            rating = float(rating_val)
        except (TypeError, ValueError):
            logger.warning("Non-numeric rating for %s: %r — defaulting to 0.0", drugbank_id, rating_val)
            rating = 0.0

        # Create property names with suffix based on directory index
        reason_rating_property = f"zero_shot_reason_rating_{index}"
        rating_property = f"zero_shot_rating_{index}"
        rating_token_length_property = f"zero_shot_rating_token_length_{index}"

        result = session.run(f"""
            MATCH (d:Drug {{drugbankId: $drugbank_id}})
            SET d.{reason_rating_property} = $reason_rating,
                d.{rating_property} = $rating,
                d.{rating_token_length_property} = $token_length
            RETURN d.drugbankId AS id
        """, drugbank_id=drugbank_id, reason_rating=reason_rating, rating=rating, token_length=token_length)

        record = result.single()
        if record and record.get("id"):
            logger.debug(f"Updated Drug node with drugbankId: {drugbank_id}")
            return True
        else:
            logger.warning(f"No Drug node matched for drugbankId: {drugbank_id}")
            return False

    except Exception as e:
        logger.error(f"An error occurred while updating the drug node {drugbank_id}: {str(e)}")
        return False


def process_json_files(directories: List[str], uri: str, user: str, password: str) -> None:
    failed_updates = 0
    total_files = 0
    updated_ok = 0
    missing_drug_nodes = 0
    parse_errors = 0

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.debug("Database connection established successfully.")

        for index, directory in enumerate(directories):
            if not os.path.isdir(directory):
                logger.warning(f"Directory does not exist or is not a directory: {directory}")
                continue

            json_files = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith('.json')]
            json_files.sort()
            logger.info(f"Directory {index+1}/{len(directories)}: {directory} → {len(json_files)} JSON files found")
            total_files += len(json_files)

            for file_path in json_files:
                drugbank_id = _extract_drugbank_id_from_filename(file_path)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        raw_text = f.read().strip()

                    # Try robust parsing
                    response_json = _parse_llm_envelope(raw_text)
                    if not isinstance(response_json, dict):
                        logger.error(f"Could not parse response JSON in file {file_path}")
                        parse_errors += 1
                        continue

                    # Update DB
                    with driver.session() as session:
                        token_length = len(raw_text)
                        ok = update_drug_node(session, drugbank_id, response_json, token_length, index)
                        if ok:
                            updated_ok += 1
                        else:
                            missing_drug_nodes += 1

                except Exception as e:
                    logger.error(f"Failed to process file {file_path}: {str(e)}")
                    failed_updates += 1

    except Exception as e:
        logger.critical(f"Failed to process JSON files or update the database: {str(e)}")
    finally:
        if 'driver' in locals():
            driver.close()

        logger.debug(f"Processed JSON files: {total_files}")
        logger.debug(f"Successful updates: {updated_ok}")
        logger.warning(f"Missing Drug nodes (no match on drugbankId): {missing_drug_nodes}")
        logger.warning(f"Files failed to parse: {parse_errors}")
        logger.warning(f"Other failures: {failed_updates}")


def _resolve_input_dirs() -> List[str]:
    # Priority: ZERO_SHOT_RATINGS_DIRS from env
    dirs = _split_dirs(ZERO_SHOT_RATINGS_DIRS_RAW)
    if dirs:
        # Keep only existing directories; warn on missing
        resolved = []
        for d in dirs:
            if os.path.isdir(d):
                resolved.append(d)
            else:
                logger.warning(f"Configured directory not found: {d}")
        return resolved

    # Fallback: outputs of Step 20
    fallback_dirs = _default_dirs_from_step20()
    if not fallback_dirs:
        logger.critical(
            "No rating directories configured via ZERO_SHOT_RATINGS_DIRS and no default output "
            "folders found at '%s/zero_shot_prompts'. You can set ZERO_SHOT_RATINGS_DIRS "
            "to one or more response directories (comma/colon separated).", RESPONSES_BASE_DIR
        )
    return fallback_dirs


def main():
    # Connection details
    uri = os.getenv("uri")
    user = os.getenv("username")
    password = os.getenv("password")

    logger.critical("=== Step 21 START: Integrate zero-shot LLM rating JSONs ===")

    dirs = _resolve_input_dirs()
    if not dirs:
        # Nothing to do, hard stop with clear context.
        logger.critical("No valid zero-shot response directories to process. Aborting Step 21.")
        return 90

    logger.info("Resolved %d zero-shot rating directories:", len(dirs))
    for i, d in enumerate(dirs, 1):
        try:
            json_count = len([f for f in os.listdir(d) if f.endswith(".json")])
        except Exception:
            json_count = 0
        logger.info("  %2d) %s (json_count=%d)", i, d, json_count)

    process_json_files(dirs, uri, user, password)

    logger.critical("=== Step 21 END: Integration finished ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())