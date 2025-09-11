# file: src/pipelines/GO_drug_classification2LLM.py
import os
import sys
import json
import logging
from typing import Optional, Dict, Any

import requests
from dotenv import load_dotenv


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


try:
    from src.utils.logging_config import setup_logging
    _use_custom_logging = True
except Exception:
    _use_custom_logging = False

# -------------------- LLM call --------------------
def call_llm(prompt: str, url: str, model: str, logger: logging.Logger) -> Optional[Dict[str, Any] | str]:
    """
    Calls an Ollama-compatible /generate endpoint with JSON format enforced.
    Returns the parsed JSON object inside the 'response' (if it parses), otherwise the raw string.
    """
    payload = {
        "model": model,
        "format": "json",     # ask the model to respond with JSON
        "prompt": prompt,
        "stream": False,      # get a single JSON object back
    }
    headers = {"Content-Type": "application/json"}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=300)
        resp.raise_for_status()
    except Exception as e:
        logger.error("LLM request failed: %s", e)
        return None

    try:
        data = resp.json()
    except Exception as e:
        logger.error("Failed to decode LLM HTTP response as JSON: %s", e)
        return None


    response_text = data.get("response")
    if not isinstance(response_text, str):
        logger.warning("Unexpected LLM response shape; 'response' not a string. Returning raw payload.")
        return data

    # Try to parse the JSON that the model produced
    try:
        parsed = json.loads(response_text)
        return parsed
    except Exception:
        # Not strictly valid JSON; return the raw text to avoid data loss
        logger.warning("Model 'response' is not valid JSON. Returning raw text.")
        return response_text


# -------------------- IO helpers --------------------
def process_json_files(input_dir: str, output_dir: str, url: str, model: str, logger: logging.Logger) -> int:
    """
    Read prompt JSON files from input_dir, call the LLM, and write responses to output_dir.
    Each input file is expected to contain: {"drugbankId": "...", "name": "...", "prompt": "..."}
    Output is written to response_<same filename>, including the original metadata.
    """
    if not os.path.isdir(input_dir):
        logger.error("Input directory does not exist or is not a directory: %s", input_dir)
        return 1

    os.makedirs(output_dir, exist_ok=True)

    files = [f for f in os.listdir(input_dir) if f.endswith(".json")]
    files.sort()
    logger.info("Found %d prompt files in %s", len(files), input_dir)

    processed = 0
    for fname in files:
        in_path = os.path.join(input_dir, fname)
        try:
            with open(in_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            logger.error("Failed reading '%s': %s", in_path, e)
            continue

        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            logger.warning("Skipping '%s' (no prompt).", in_path)
            continue

        drugbank_id = payload.get("drugbankId")
        name = payload.get("name")

        llm_result = call_llm(prompt, url=url, model=model, logger=logger)
        if llm_result is None:
            logger.error("LLM call failed for '%s'.", fname)
            continue

        out_name = f"response_{fname}"
        out_path = os.path.join(output_dir, out_name)
        out_payload = {
            "drugbankId": drugbank_id,
            "name": name,
            "response": llm_result,
            "model": model,
        }
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(out_payload, f, indent=2, ensure_ascii=False)
            processed += 1
            logger.info("Wrote LLM response → %s", out_path)
        except Exception as e:
            logger.error("Failed writing response for '%s': %s", fname, e)

    logger.info("Processed %d/%d files.", processed, len(files))
    return 0 if processed > 0 else 2


# -------------------- Main --------------------
def main() -> int:
    load_dotenv()

    # Gate: only run if RUN_LLM=true
    run_llm = (os.getenv("RUN_LLM", "false").strip().lower() == "true")
    if not run_llm:
        # Quietly succeed so the pipeline can keep going without LLM steps
        print("RUN_LLM=false → Skipping GO drug classification LLM step.")
        return 0

    # Logging
    if _use_custom_logging:
        setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
    else:
        logging.basicConfig(
            level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s | %(message)s",
        )
    logger = logging.getLogger(__name__)

    # Paths & LLM config
    input_dir = os.getenv("GO_CLASSIFICATION_PROMPTS_DIR", "/app/exports/GO_classification_prompts")
    output_dir = os.getenv("GO_CLASSIFICATION_RESPONSES_DIR", "reprod/llm_outputs/GO_classification_responses")
    llm_url = os.getenv("LLM_URL", "http://ollama:11434/api/generate")
    llm_model = os.getenv("LLM_MODEL", "llama3:8b")

    logger.critical("=== Step 28 START: GO drug classification → LLM ===")
    logger.info("Input prompts:  %s", input_dir)
    logger.info("Output folder:  %s", output_dir)
    logger.info("LLM endpoint:   %s", llm_url)
    logger.info("LLM model:      %s", llm_model)

    rc = process_json_files(input_dir, output_dir, url=llm_url, model=llm_model, logger=logger)

    if rc == 0:
        logger.info("GO drug classification LLM step completed successfully.")
    elif rc == 2:
        logger.warning("GO drug classification LLM step ran but produced no outputs.")
    else:
        logger.error("GO drug classification LLM step failed (rc=%d).", rc)

    logger.critical("=== Step 28 END ===")
    return rc


if __name__ == "__main__":
    sys.exit(main())