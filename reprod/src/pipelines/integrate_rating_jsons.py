# file: src/pipelines/integrate_rating_jsons.py
"""
Integrate LLM rating JSONs into Neo4j :Drug nodes with robust parsing and detailed, console-visible logging.
Handles:
  - Proper JSON dict files
  - JSON strings that contain a JSON object (double-encoded)
  - Envelopes from run_llm_on_prompts.py (parsed/raw_response)
  - Minor encoding anomalies (BOM/whitespace)
"""

import os, sys, json, logging, codecs
from typing import List, Set, Dict, Tuple, Optional
from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.logging_config import setup_logging
from src.utils.conn_neo4j import Neo4jConnection

# ---------- Logging helpers ----------

def _ensure_console_logging() -> None:
    """Ensure logs appear on docker stdout even if only file handlers are configured."""
    root = logging.getLogger()
    has_stream = any(isinstance(h, logging.StreamHandler) for h in root.handlers)
    if not has_stream:
        sh = logging.StreamHandler()
        sh.setLevel(root.level or logging.INFO)
        sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s | %(message)s"))
        root.addHandler(sh)

# ---------- Env & DB helpers ----------

def _resolve_env() -> Tuple[List[str], str, str, str, str]:
    load_dotenv()
    raw_dirs = os.getenv("RATINGS_DIRS", "/app/exports/llm_responses/iteration_1")
    # allow comma or colon separators
    parts = [p.strip() for token in raw_dirs.split(",") for p in token.split(":")]
    dirs = [os.path.abspath(p) for p in parts if p]

    uri = os.getenv("uri", "bolt://neo4j:7687")
    user = os.getenv("username", "neo4j")
    pwd  = os.getenv("password")
    neo_auth = os.getenv("NEO4J_AUTH", "")
    if not pwd and neo_auth.startswith("neo4j/"):
        pwd = neo_auth[len("neo4j/"):]
    if not pwd:
        raise RuntimeError("Neo4j password not provided via 'password' or 'NEO4J_AUTH'.")
    return dirs, raw_dirs, uri, user, pwd

def _all_db_drug_ids(conn: Neo4jConnection) -> Set[str]:
    ids: Set[str] = set()
    with conn.driver.session() as session:
        for rec in session.run("MATCH (d:Drug) RETURN d.drugbankId AS id"):
            if rec["id"]:
                ids.add(rec["id"])
    logging.info("Collected %d Drug nodes from DB.", len(ids))
    return ids

# ---------- JSON coercion & extraction ----------

def _read_text_file(path: str) -> str:
    """
    Read file as UTF-8 (with BOM tolerance). Replace invalid bytes rather than failing.
    Trim NULs and whitespace.
    """
    with open(path, "rb") as fh:
        raw = fh.read()
    # Strip BOM if present
    if raw.startswith(codecs.BOM_UTF8):
        raw = raw[len(codecs.BOM_UTF8):]
    text = raw.decode("utf-8", errors="replace")
    # Remove stray NULs and trim
    return text.replace("\x00", "").strip()

def _json_load_best_effort(text: str):
    """
    Try to parse a JSON string. If it yields a string, try to parse again (double-encoded case).
    If it yields a single-item list with dict, accept that dict.
    Return dict/obj or original on failure.
    """
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        logging.error("JSON load error: %s ... (first 100 chars: %r)", e, text[:100])
        return text

    # If the file contained a JSON string of a JSON object
    if isinstance(obj, str):
        try:
            obj2 = json.loads(obj)
            return obj2
        except Exception:
            return obj

    # Tolerate single-item list wrapping
    if isinstance(obj, list) and len(obj) == 1 and isinstance(obj[0], dict):
        return obj[0]

    return obj

def _coerce_to_dict(payload) -> Optional[dict]:
    """
    Accept:
      - dict (ideal)
      - list with single dict (rare)
      - string containing JSON -> parsed into dict
    Return dict or None.
    """
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list) and len(payload) == 1 and isinstance(payload[0], dict):
        return payload[0]
    if isinstance(payload, str):
        parsed = _json_load_best_effort(payload)
        return parsed if isinstance(parsed, dict) else None
    logging.error("Unsupported payload type: %s", type(payload).__name__)
    return None

def _infer_drugbank_id(filename: str, payload: dict) -> Optional[str]:
    # Prefer explicit field if present
    if "drugbankId" in payload and str(payload["drugbankId"]).strip():
        return str(payload["drugbankId"]).strip()
    base = os.path.splitext(os.path.basename(filename))[0]
    return base[len("response_"):] if base.startswith("response_") else base

def _normalize_rating_value(val) -> float:
    """
    Convert rating to float and clamp to [0,1], with warnings if coercion/clamp was needed.
    """
    original = val
    try:
        r = float(val)
    except Exception:
        logging.warning("Rating value %r is not numeric; coercing to 0.0.", original)
        return 0.0
    if r < 0.0 or r > 1.0:
        logging.warning("Rating value %.4f out of [0,1]; clamping.", r)
        r = max(0.0, min(1.0, r))
    return r

def _extract_rating(payload: dict) -> Optional[Dict[str, object]]:
    """
    Accept both:
      - direct rating: {"reason_rating": "...", "rating": 0.42}
      - envelope (from run_llm_on_prompts): has "parsed" and/or "raw_response"
    """
    # Direct
    if "reason_rating" in payload and "rating" in payload:
        rr = payload.get("reason_rating", "")
        r  = _normalize_rating_value(payload.get("rating", 0.0))
        return {"reason_rating": rr, "rating": r}

    # Envelope: parsed may already contain rating, or a stringified "response"
    parsed = payload.get("parsed")
    if isinstance(parsed, dict):
        if "reason_rating" in parsed and "rating" in parsed:
            return {"reason_rating": parsed.get("reason_rating",""),
                    "rating": _normalize_rating_value(parsed.get("rating", 0.0))}
        resp = parsed.get("response")
        if isinstance(resp, str):
            inner = _json_load_best_effort(resp)
            if isinstance(inner, dict) and "reason_rating" in inner and "rating" in inner:
                return {"reason_rating": inner.get("reason_rating",""),
                        "rating": _normalize_rating_value(inner.get("rating", 0.0))}

    # Last resort: raw_response -> response -> rating
    raw = payload.get("raw_response")
    if isinstance(raw, str):
        outer = _json_load_best_effort(raw)
        if isinstance(outer, dict):
            resp = outer.get("response")
            if isinstance(resp, str):
                inner = _json_load_best_effort(resp)
                if isinstance(inner, dict) and "reason_rating" in inner and "rating" in inner:
                    return {"reason_rating": inner.get("reason_rating",""),
                            "rating": _normalize_rating_value(inner.get("rating", 0.0))}
    return None

# ---------- Neo4j write ----------

def _update_drug(session, drugbank_id: str, rating: Dict[str, object], idx: int) -> None:
    rr_key = f"reason_rating_{idx}"
    r_key  = f"rating_{idx}"
    session.run(
        f"""
        MATCH (d:Drug {{drugbankId: $id}})
        SET d.{rr_key} = $rr,
            d.{r_key}  = $r
        """,
        id=drugbank_id, rr=str(rating.get("reason_rating","")), r=float(rating.get("rating",0.0))
    )

# ---------- Directory processing ----------

def _count_files(path: str) -> int:
    try:
        return len([f for f in os.listdir(path) if f.endswith(".json")])
    except Exception:
        return 0

def _load_json_file_to_dict(path: str) -> Optional[dict]:
    """
    Load a file and produce a dict using the robust coercion rules:
      - parse JSON
      - if yields string, parse again
      - if single-item list with dict, accept dict
    """
    text = _read_text_file(path)
    obj = _json_load_best_effort(text)
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, str):
        # Try one more forced pass (covers deeply double-encoded cases)
        obj2 = _json_load_best_effort(obj.strip())
        if isinstance(obj2, dict):
            return obj2
    if isinstance(obj, list) and len(obj) == 1 and isinstance(obj[0], dict):
        return obj[0]
    return None

def _integrate_directory(conn: Neo4jConnection, path: str, idx: int,
                         db_ids: Set[str], rated: Set[str], bogus: Set[str]) -> Tuple[int,int,int]:
    seen=applied=failed=0
    if not os.path.isdir(path):
        logging.warning("Ratings directory missing or not a directory: %s", path)
        return (0,0,0)

    files = sorted(f for f in os.listdir(path) if f.endswith(".json"))
    logging.info("Directory %d: %s → %d JSON files found", idx, path, len(files))

    sample_success: List[str] = []

    with conn.driver.session() as session:
        for fn in files:
            seen += 1
            fpath = os.path.join(path, fn)
            payload = _load_json_file_to_dict(fpath)
            if payload is None:
                logging.error("Unsupported or malformed JSON in %s; skipping.", fpath)
                failed += 1
                continue

            drug_id = _infer_drugbank_id(fn, payload)
            if not drug_id:
                logging.warning("Could not infer drugbankId from filename %s; skipping.", fn)
                failed += 1
                continue

            rating = _extract_rating(payload)
            if not rating:
                logging.warning("No rating extracted for %s (file: %s); skipping.", drug_id, fn)
                failed += 1
                continue

            if drug_id not in db_ids:
                bogus.add(drug_id)
                continue

            try:
                _update_drug(session, drug_id, rating, idx)
                applied += 1
                rated.add(drug_id)
                if len(sample_success) < 5:
                    sample_success.append(f"{drug_id}=>{rating.get('rating')}")
            except Exception as e:
                logging.error("Neo4j update failed for %s: %s", drug_id, e)
                failed += 1

    logging.info("Directory %d summary: seen=%d, applied=%d, failed=%d", idx, seen, applied, failed)
    if sample_success:
        logging.info("Directory %d sample applied ratings: %s", idx, ", ".join(sample_success))
    return seen, applied, failed

# ---------- Main ----------

def main() -> int:
    setup_logging()
    _ensure_console_logging()

    dirs, raw_dirs, uri, user, pwd = _resolve_env()

    logging.critical("=== Step 13 START: Integrate LLM rating JSONs ===")
    logging.critical("RATINGS_DIRS (raw) = %r", raw_dirs)

    if not dirs:
        logging.critical("No rating directories resolved from RATINGS_DIRS. Nothing to integrate.")
        logging.critical("=== Step 13 END (no-op) ===")
        return 0

    for i, d in enumerate(dirs, start=1):
        logging.info("Resolved directory %d: %s (json_count=%d)", i, d, _count_files(d))
    logging.critical("Total rating directories: %d", len(dirs))

    bogus_ids: Set[str] = set()
    rated_ids: Set[str] = set()
    totals = {"seen": 0, "applied": 0, "failed": 0}

    try:
        with Neo4jConnection(uri, user, pwd) as conn:
            db_ids = _all_db_drug_ids(conn)

            for idx, d in enumerate(dirs, start=1):
                seen, applied, failed = _integrate_directory(conn, d, idx, db_ids, rated_ids, bogus_ids)
                totals["seen"] += seen
                totals["applied"] += applied
                totals["failed"] += failed

            # Compute unrated DB drugs for warnings
            unrated = sorted(db_ids - rated_ids)

    except Exception as e:
        logging.critical("Integration crashed: %s", e)
        logging.critical("=== Step 13 END (error) ===")
        return 1

    # Summaries
    logging.critical("Integration totals: JSON files seen=%d, applied=%d, failed=%d",
                     totals["seen"], totals["applied"], totals["failed"])

    if bogus_ids:
        logging.warning("Dropped %d JSONs for non-existent DrugBank IDs. Examples: %s",
                        len(bogus_ids), ", ".join(sorted(list(bogus_ids))[:10]))
    else:
        logging.info("No JSONs referenced non-existent DrugBank IDs.")

    if unrated:
        logging.warning("%d DB Drug nodes received no rating from the provided directories. Examples: %s",
                        len(unrated), ", ".join(unrated[:10]))
    else:
        logging.info("All DB Drug nodes were rated at least once from the provided directories.")

    logging.critical("=== Step 13 END ===")
    return 0

if __name__ == "__main__":
    sys.exit(main())