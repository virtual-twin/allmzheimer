"""
Run LLM over previously generated prompt JSONs.

Default behaviour: SKIP (RUN_LLM=false) to avoid consuming local resources.
Enable via .env:
  RUN_LLM=true
  LLM_URL=http://localhost:11434/api/generate     # adapt to your LLM endpoint if you are using an external LLM API (compare README.md)
  LLM_MODEL=llama3:8b                              # model name for your endpoint (in case you want to use a different model than llama3:8b that we used in the paper)
Optional env:
  PROMPTS_DIR=/app/exports/prompts                 # legacy single-dir var (still supported)
  PROMPTS_DIRS=/app/exports/prompts:/app/exports/prompts/zero_shot_prompts
  RESPONSES_DIR=/app/exports/llm_responses
  LOG_DIR=/app/logs/llm_runs
  ITERATIONS=1
  START_ITERATION=1
  LOG_LEVEL=INFO|DEBUG|WARNING|ERROR|CRITICAL
"""

import os
import sys
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Optional, List

import requests
from dotenv import load_dotenv

# Ensure project root is on path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.logging_config import setup_logging  # reuses project logging defaults


# ----------- Configuration ----------------
load_dotenv()

RUN_LLM        = os.getenv("RUN_LLM", "false").lower() in {"1", "true", "yes"}
LLM_URL = os.getenv("LLM_URL", "http://ollama:11434/api/generate")
LLM_MODEL      = os.getenv("LLM_MODEL", "llama3:8b")

# Backward compat: PROMPTS_DIR (singular). New: PROMPTS_DIRS supports multiple paths via comma/colon.
PROMPTS_DIR_LEGACY = os.getenv("PROMPTS_DIR", "/app/exports/prompts")
PROMPTS_DIRS_RAW   = os.getenv("PROMPTS_DIRS", "").strip()
RESPONSES_DIR      = os.getenv("RESPONSES_DIR", "/app/exports/llm_responses")
LOG_BASE_DIR       = os.getenv("LOG_DIR", "/app/logs/llm_runs")

ITERATIONS         = int(os.getenv("ITERATIONS", "1"))
START_ITER         = int(os.getenv("START_ITERATION", "1"))
# Please note - if you get LLM timeout errors (error code 500) you can increase this timeout by setting the LLM_HTTP_TIMEOUT variable in the .env file
# However, if 240 seconds are not enough, the infrastructure you run the code on is not recommended for running the rating steps and setting 
# RUN_LLM to false (or using an external LLM API) is highly recommended
HTTP_TIMEOUT_S     = float(os.getenv("LLM_HTTP_TIMEOUT", "240.0"))

# Optional explicit log level override for this module
ENV_LOG_LEVEL      = os.getenv("LOG_LEVEL", "").upper()


def _setup_rotating_logging(iteration: int) -> str:
    """
    Extend the project's logging with a rotating file handler per iteration.
    """
    # Initialize project logging once
    setup_logging()

    if ENV_LOG_LEVEL:
        level = getattr(logging, ENV_LOG_LEVEL, logging.INFO)
        logging.getLogger().setLevel(level)

    ts_date = datetime.now().strftime("%Y%m%d")
    ts_full = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(LOG_BASE_DIR, ts_date, f"iteration_{iteration}")
    os.makedirs(run_dir, exist_ok=True)
    log_path = os.path.join(run_dir, f"log_{ts_full}.log")

    handler = RotatingFileHandler(log_path, maxBytes=10 * 1024 * 1024, backupCount=5)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    root = logging.getLogger()
    root.addHandler(handler)

    logging.info("Additional rotating log attached: %s", log_path)
    return log_path


def _call_llm(prompt: str) -> Optional[dict]:
    """
    Call the configured LLM endpoint with a JSON body compatible with Ollama's /api/generate.
    Returns a dict containing fields:
      - ok: bool
      - raw_text: str (raw response text)
      - parsed: object | None (parsed JSON if possible)
      - status_code: int
    """
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": LLM_MODEL,
        "format": "json",
        "prompt": prompt,
        "stream": False,
    }

    try:
        resp = requests.post(LLM_URL, headers=headers, data=json.dumps(payload), timeout=HTTP_TIMEOUT_S)
        raw = resp.text
        parsed = None
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = None

        if resp.status_code == 200:
            # Ollama returns {"response": "..."} when format=json is set; some models return JSON string in "response"

            logging.info("LLM call OK (HTTP 200).")
            return {"ok": True, "raw_text": raw, "parsed": parsed, "status_code": resp.status_code}
        else:
            logging.error("LLM call failed: HTTP %s, body: %s", resp.status_code, raw)
            return {"ok": False, "raw_text": raw, "parsed": parsed, "status_code": resp.status_code}

    except Exception as e:
        logging.error("LLM call raised exception: %s", e)
        return {"ok": False, "raw_text": str(e), "parsed": None, "status_code": -1}


def _process_json_files(input_dir: str, output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)

    try:
        files = [fn for fn in os.listdir(input_dir) if fn.endswith(".json")]
    except FileNotFoundError:
        logging.error("Prompts directory does not exist: %s", input_dir)
        return

    files.sort()  # deterministic ordering
    logging.info("Discovered %d prompt files in %s", len(files), input_dir)

    for filename in files:
        in_path = os.path.join(input_dir, filename)
        try:
            with open(in_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logging.error("Failed to load %s: %s", in_path, e)
            continue

        prompt = data.get("prompt", "")
        drugbank_id = data.get("drugbankId", "unknown")
        out_path = os.path.join(output_dir, f"response_{filename}")

        result = _call_llm(prompt)
        if not result or not result.get("ok"):
            logging.error("Skipping write for %s due to failed LLM call.", filename)
            continue

        # Persist a rich envelope for provenance
        envelope = {
            "drugbankId": drugbank_id,
            "name": data.get("name"),
            "model": LLM_MODEL,
            "llm_url": LLM_URL,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "raw_response": result["raw_text"],
            "parsed": result["parsed"],
        }

        try:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(envelope, f, indent=2, ensure_ascii=False)
            logging.info("Saved LLM response to %s", out_path)
        except Exception as e:
            logging.error("Failed to write %s: %s", out_path, e)


def _parse_prompts_dirs() -> List[str]:
    """
    Return a list of prompt directories.
    Preference: PROMPTS_DIRS (comma/colon-separated). Fallback: PROMPTS_DIR (legacy).
    """
    if PROMPTS_DIRS_RAW:
        # split on comma and colon, strip spaces, keep non-empty
        parts = []
        for chunk in PROMPTS_DIRS_RAW.split(","):
            parts.extend(chunk.split(":"))
        dirs = [p.strip() for p in parts if p.strip()]
        if dirs:
            return dirs
    # fallback
    return [PROMPTS_DIR_LEGACY]


def main() -> int:
    # Attach project logging and per-run rotating file
    log_file = _setup_rotating_logging(START_ITER)

    prompt_dirs = _parse_prompts_dirs()

    # Default: skip LLM execution
    if not RUN_LLM:
        # Log the list of prompt dirs for reviewer clarity
        logging.critical(
            "Skipping LLM execution by default (RUN_LLM=false). "
            "Reviewers may proceed with the provided prompt JSONs as dataset artifacts in %s. "
            "To run this step, set RUN_LLM=true in .env and configure LLM_URL to your model endpoint. "
            "For a local setup using Ollama, see: https://ollama.com (typical endpoint: %s). "
            "Log file: %s",
            prompt_dirs, LLM_URL, log_file
        )
        return 0

    # When enabled, run for ITERATIONS starting at START_ITER
    for i in range(ITERATIONS):
        iter_no = START_ITER + i
        # add a new rotating file per iteration for clarity
        log_file_iter = _setup_rotating_logging(iter_no)
        logging.critical(  # CRITICAL per request for reviewers’ attention
            "Running LLM over prompts (iteration=%d). Endpoint: %s | Model: %s | Responses base: %s | Log file: %s",
            iter_no, LLM_URL, LLM_MODEL, RESPONSES_DIR, log_file_iter
        )

        for pdir in prompt_dirs:
            label = os.path.basename(os.path.normpath(pdir)) or "prompts"
            out_dir = os.path.join(RESPONSES_DIR, label, f"iteration_{iter_no}")
            logging.info("Processing prompts dir '%s' → responses dir '%s'", pdir, out_dir)
            _process_json_files(pdir, out_dir)

        logging.info("Finished processing all prompt directories for iteration %d.", iter_no)

    return 0


if __name__ == "__main__":
    sys.exit(main())