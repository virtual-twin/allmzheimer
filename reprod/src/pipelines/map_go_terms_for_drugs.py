# file: src/pipelines/map_go_terms_for_drugs.py
"""
Map natural-language GO biological process names on Drug nodes to GO term IDs via QuickGO.

Strategy:
- Read all Drug nodes with non-empty d.affectedGoProcess.
- Normalize & deduplicate process strings -> unique set of terms.
- Concurrently fetch GO IDs for unique terms (HTTP only; no DB in threads).
- Persist a cache of {term -> go_id or None} for reproducibility.
- Compute per-drug GO ID lists and write back in batched Cypher via UNWIND.

Env (optional):
  LOG_LEVEL=INFO|DEBUG|...
  GO_FETCH_MAX_WORKERS=6
  GO_FETCH_MAX_RETRIES=4
  GO_FETCH_BACKOFF=0.5
  GO_FETCH_TIMEOUT=10.0
  GO_MAP_CACHE=/app/datasets/cache/go_map.json
  BATCH_WRITE_SIZE=500
  uri, username, password (or NEO4J_AUTH) for Neo4j connection
"""

import os, sys, json, time, logging, random
from typing import Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests
from requests.exceptions import RequestException, Timeout
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from dotenv import load_dotenv

# Project root on path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.logging_config import setup_logging
from src.utils.conn_neo4j import Neo4jConnection

# --- Tunables (env-overridable) ---
# please keep this reasonable to respect the QuickGO API rate limits
MAX_WORKERS      = int(os.getenv("GO_FETCH_MAX_WORKERS", "6"))
MAX_RETRIES      = int(os.getenv("GO_FETCH_MAX_RETRIES", "4"))
BACKOFF_FACTOR   = float(os.getenv("GO_FETCH_BACKOFF", "0.5"))
HTTP_TIMEOUT     = float(os.getenv("GO_FETCH_TIMEOUT", "10.0"))   # seconds
CACHE_PATH       = os.getenv("GO_MAP_CACHE", "/app/datasets/cache/go_map.json")
BATCH_WRITE_SIZE = int(os.getenv("BATCH_WRITE_SIZE", "500"))

# QuickGO endpoint (term -> GO id)
QUICKGO_URL = "https://www.ebi.ac.uk/QuickGO/services/ontology/go/search"

# --- HTTP session with retries & pooling ------------------------------------

def _make_http_session() -> requests.Session:
    sess = requests.Session()
    adapter = HTTPAdapter(
        pool_connections=max(16, MAX_WORKERS * 2),
        pool_maxsize=max(16, MAX_WORKERS * 2),
        max_retries=Retry(
            total=MAX_RETRIES,
            connect=MAX_RETRIES,
            read=MAX_RETRIES,
            status=MAX_RETRIES,
            backoff_factor=BACKOFF_FACTOR,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET"]),
            raise_on_status=False,
            respect_retry_after_header=True,
        ),
    )
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    sess.headers.update({
        "Accept": "application/json",
        "User-Agent": "alz-reprod-pipeline/1.0 (QuickGO-only) python-requests",
    })
    return sess

_HTTP = _make_http_session()

def _jitter_delay(base: float, attempt: int) -> float:
    # exponential backoff with jitter in [0.5, 1.5]x
    return (base * (2 ** attempt)) * random.uniform(0.5, 1.5)

# --- Helpers -----------------------------------------------------------------

def _norm_term(s: str) -> str:
    """Lowercase, collapse whitespace; stable normalization for cache keys."""
    return " ".join(s.strip().split()).lower()

def _load_cache(path: str) -> Dict[str, Optional[str]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {str(k): (v if v is None else str(v)) for k, v in data.items()}
    except Exception:
        pass
    return {}

def _save_cache(path: str, mapping: Dict[str, Optional[str]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)

# --- QuickGO resolver (only) -------------------------------------------------

def _fetch_go_id(term: str) -> Optional[str]:
    """Fetch GO ID for a normalized term via QuickGO; return None if not found."""
    params = {"query": term, "limit": 1, "ontology": "go"}
    for attempt in range(MAX_RETRIES):
        try:
            r = _HTTP.get(QUICKGO_URL, params=params, timeout=HTTP_TIMEOUT)
            if r.status_code == 200:
                payload = r.json()
                res = payload.get("results") or []
                if res:
                    return res[0].get("id")
                return None
            if r.status_code in (429, 500, 502, 503, 504):
                wait = _jitter_delay(BACKOFF_FACTOR, attempt)
                logging.warning("QuickGO %s for term '%s'; retrying in %.2fs",
                                r.status_code, term, wait)
                time.sleep(wait)
                continue
            logging.error("QuickGO %s for term '%s' (no retry).", r.status_code, term)
            return None
        except (RequestException, Timeout) as e:
            wait = _jitter_delay(BACKOFF_FACTOR, attempt)
            logging.warning("QuickGO request error for term '%s' (attempt %d/%d): %s; retrying in %.2fs",
                            term, attempt + 1, MAX_RETRIES, e, wait)
            time.sleep(wait)
    logging.error("QuickGO exhausted retries for term '%s'", term)
    return None

# --- Neo4j I/O ---------------------------------------------------------------

def _collect_drug_terms(conn: Neo4jConnection) -> List[Tuple[str, List[str]]]:
    """
    Return list of (drugbankId, affectedGoProcessTerms[]) for drugs with non-empty affectedGoProcess.
    """
    query = (
        "MATCH (d:Drug) "
        "WHERE d.affectedGoProcess IS NOT NULL AND size(d.affectedGoProcess) > 0 "
        "RETURN d.drugbankId AS drugbankId, d.affectedGoProcess AS terms"
    )
    rows: List[Tuple[str, List[str]]] = []
    with conn.driver.session() as session:
        for rec in session.run(query):
            dbid = rec["drugbankId"]
            raw = rec["terms"]
            if isinstance(raw, list):
                terms = [t for t in raw if isinstance(t, str) and t.strip()]
            elif isinstance(raw, str):
                terms = [t for t in raw.split(",") if t.strip()]
            else:
                terms = []
            rows.append((dbid, terms))
    logging.info("Collected %d Drug nodes with affectedGoProcess.", len(rows))
    return rows

def _build_unique_terms(rows: List[Tuple[str, List[str]]]) -> List[str]:
    uniq = set()
    for _, terms in rows:
        for t in terms:
            uniq.add(_norm_term(t))
    items = sorted(uniq)
    logging.info("Identified %d unique normalized GO process terms.", len(items))
    return items

def _resolve_terms(terms: List[str], cache: Dict[str, Optional[str]]) -> Dict[str, Optional[str]]:
    """
    Return mapping term->go_id (possibly None). Uses cache and fetches missing concurrently.
    """
    resolved: Dict[str, Optional[str]] = dict(cache)  # copy
    pending = [t for t in terms if t not in resolved]
    logging.info("Resolving %d uncached terms via QuickGO (workers=%d).", len(pending), MAX_WORKERS)

    if pending:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futs = {ex.submit(_fetch_go_id, term): term for term in pending}
            for fut in as_completed(futs):
                term = futs[fut]
                try:
                    goid = fut.result()
                    resolved[term] = goid
                except Exception as e:
                    logging.error("Unexpected error resolving term '%s': %s", term, e)
                    resolved[term] = None
    return resolved

def _build_updates(rows: List[Tuple[str, List[str]]],
                   mapping: Dict[str, Optional[str]]) -> List[Dict[str, object]]:
    """
    For each drug, map its terms -> GO IDs (deduped), returning rows suitable for UNWIND.
    """
    updates: List[Dict[str, object]] = []
    for drugbankId, terms in rows:
        ids = []
        seen = set()
        for t in terms:
            nt = _norm_term(t)
            goid = mapping.get(nt)
            if goid and goid not in seen:
                seen.add(goid)
                ids.append(goid)
        updates.append({"drugbankId": drugbankId, "goIds": ids})
    logging.info("Prepared update payload for %d Drug nodes.", len(updates))
    return updates

def _chunk(lst: List[dict], n: int) -> List[List[dict]]:
    return [lst[i:i+n] for i in range(0, len(lst), n)]

def _write_updates(conn: Neo4jConnection, updates: List[Dict[str, object]]) -> None:
    """
    Batched write: set d.affectedGoProcessId and simple provenance.
    """
    if not updates:
        logging.info("No updates to write.")
        return

    ts = datetime.now(timezone.utc).isoformat()
    query = (
        "UNWIND $rows AS row "
        "MATCH (d:Drug {drugbankId: row.drugbankId}) "
        "SET d.affectedGoProcessId = row.goIds, "
        "    d.affectedGoProcessId_provenance = 'QuickGO search', "
        "    d.affectedGoProcessId_cachedAt = datetime($ts)"
    )
    total = 0
    with conn.driver.session() as session:
        for batch in _chunk(updates, BATCH_WRITE_SIZE):
            summary = session.run(query, rows=batch, ts=ts).consume().counters
            total += len(batch)
            logging.info(
                "Wrote batch of %d updates (properties_set=%d, relationships_created=%d).",
                len(batch), summary.properties_set, summary.relationships_created
            )
    logging.info("Completed writing %d Drug updates.", total)

# --- Orchestration -----------------------------------------------------------

def _resolve_creds() -> Tuple[str, str, str]:
    """
    Resolve Neo4j credentials from env with NEO4J_AUTH fallback.
    """
    load_dotenv()
    uri = os.getenv("uri", "bolt://neo4j:7687")
    user = os.getenv("username", "neo4j")
    pwd  = os.getenv("password")
    if not pwd and os.getenv("NEO4J_AUTH", "").startswith("neo4j/"):
        pwd = os.getenv("NEO4J_AUTH")[len("neo4j/"):]
    if not pwd:
        raise RuntimeError("Neo4j password not provided via 'password' or NEO4J_AUTH.")
    return uri, user, pwd

def main() -> None:
    setup_logging()
    uri, user, pwd = _resolve_creds()
    logging.info("Starting GO term mapping for Drug nodes.")

    with Neo4jConnection(uri=uri, user=user, password=pwd) as conn:
        rows = _collect_drug_terms(conn)
        if not rows:
            logging.info("No Drug nodes require GO mapping; exiting.")
            return

        terms = _build_unique_terms(rows)
        cache = _load_cache(CACHE_PATH)
        mapping = _resolve_terms(terms, cache)
        _save_cache(CACHE_PATH, mapping)
        logging.info("Cache saved to %s", CACHE_PATH)

        updates = _build_updates(rows, mapping)
        _write_updates(conn, updates)

    logging.info("GO term mapping finished successfully.")

if __name__ == "__main__":
    main()