import os
import json
import csv
import requests
import logging
import numpy as np
from typing import Dict, List, Optional

# ---------------- Paths / Env ----------------
EXPORTS_DIR = "/app/exports"


TOP_DIR = os.getenv("TOP100_DIR", os.getenv("TOP100_EXPORT_DIR", "/app/exports/top_100_drugs_for_umap_plot"))

STATS_DIR = os.path.join(EXPORTS_DIR, "stats")
os.makedirs(STATS_DIR, exist_ok=True)

STATIC_CSV = os.getenv("TOP100_STATIC_CSV", os.path.join(TOP_DIR, "ontological_prompt_top_100.csv"))
ZS_CSV     = os.getenv("TOP100_ZS_CSV",     os.path.join(TOP_DIR, "zero_shot_top_100.csv"))

LITERATURE_JSON = os.path.join("/app/datasets", "cummings_eta_al_AD_DR_candidates.json")

# Ollama inside Docker Compose
EMBED_URL   = os.getenv("OLLAMA_URL", "http://ollama:11434/api/embed")
EMBED_MODEL = os.getenv("EMBED_MODEL", "llama3:8b")

# ---------------- Logging ----------------
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def _read_top_csv(csv_path: str, top_n: int) -> List[str]:
    """
    Read a ranked CSV with header including a 'name' column and return first top_n names.
    Assumes file is already sorted by total_rating DESC (as our generator does).
    """
    if not os.path.exists(csv_path):
        logger.critical("Top list CSV not found: %s", csv_path)
        return []
    names: List[str] = []
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= top_n:
                break
            name = row.get("name")
            if name:
                names.append(name)
    logger.info("Loaded top %d from %s (count=%d).", top_n, csv_path, len(names))
    return names

def _read_literature(json_path: str) -> List[str]:
    if not os.path.exists(json_path):
        logger.critical("Literature JSON not found: %s", json_path)
        return []
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Accept list or dict (names as keys)
    if isinstance(data, dict):
        names = list(data.keys())
    elif isinstance(data, list):
        names = data
    else:
        logger.critical("Unexpected literature JSON structure; expected list or dict: %s", json_path)
        names = []
    logger.info("Loaded literature list: %d drugs", len(names))
    return names

def get_embedding_for_drug(drug: str, model: str) -> Optional[np.ndarray]:
    payload = {"model": model, "input": drug}
    try:
        resp = requests.post(EMBED_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()
        emb_list = data.get("embeddings", [[]])[0]
        if not emb_list:
            logger.error("Empty embedding for '%s'", drug)
            return None
        return np.array(emb_list, dtype=float)
    except requests.RequestException as err:
        logger.error("Embedding request failed for '%s': %s", drug, err)
        return None

def embed_drugs(drug_list: List[str], model: str) -> Dict[str, np.ndarray]:
    embs: Dict[str, np.ndarray] = {}
    for drug in drug_list:
        e = get_embedding_for_drug(drug, model)
        if e is not None:
            embs[drug] = e
        else:
            logger.warning("Skipping '%s' (embedding failed).", drug)
    return embs

def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    d = float(np.dot(v1, v2))
    n1 = float(np.linalg.norm(v1))
    n2 = float(np.linalg.norm(v2))
    if n1 == 0.0 or n2 == 0.0:
        return 0.0
    return d / (n1 * n2)

def minimal_distances_to_literature(approach_embs: Dict[str, np.ndarray],
                                    lit_embs: Dict[str, np.ndarray]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    if not lit_embs:
        return out
    lit_vals = list(lit_embs.values())
    for drug, emb in approach_embs.items():
        # min over all literature
        min_dist = float("inf")
        for l_emb in lit_vals:
            sim = cosine_similarity(emb, l_emb)
            dist = 1.0 - sim
            if dist < min_dist:
                min_dist = dist
        out[drug] = min_dist
    return out

def summarize_distances(dists: Dict[str, float]) -> Dict[str, float]:
    if not dists:
        return {"total_distance": float("nan"),
                "avg_distance": float("nan"),
                "min_distance": float("nan"),
                "max_distance": float("nan"),
                "num_drugs": 0}
    vals = list(dists.values())
    return {
        "total_distance": float(np.sum(vals)),
        "avg_distance": float(np.mean(vals)),
        "min_distance": float(np.min(vals)),
        "max_distance": float(np.max(vals)),
        "num_drugs": len(vals),
    }

def main() -> int:
    # Sanity: warn if someone tries to use “first half of top-100 JSONs”
    json_static = os.path.join(TOP_DIR, "static_prompt_top_100.json")
    json_zs     = os.path.join(TOP_DIR, "zero_shot_prompt_top_100.json")
    if os.path.exists(json_static) or os.path.exists(json_zs):
        logger.warning("Detected JSON top-100 files. These may NOT be sorted. "
                       "This script uses the CSVs which ARE sorted by total_rating.")


    static_top50 = _read_top_csv(STATIC_CSV, top_n=50)
    zs_top50     = _read_top_csv(ZS_CSV, top_n=50)

    if not static_top50 or not zs_top50:
        logger.critical("Missing top-50 lists. Ensure Step 22 produced the CSVs in %s", TOP_DIR)
        return 1

    literature_list = _read_literature(LITERATURE_JSON)
    if not literature_list:
        logger.critical("Literature list empty; cannot proceed.")
        return 1

    logger.info("Embedding using endpoint=%s model=%s", EMBED_URL, EMBED_MODEL)

    # Embed all sets
    static_embs = embed_drugs(static_top50, EMBED_MODEL)
    zs_embs     = embed_drugs(zs_top50, EMBED_MODEL)
    lit_embs    = embed_drugs(literature_list, EMBED_MODEL)

    # Compute minimal distances to literature (cummings et al)
    static_dists = minimal_distances_to_literature(static_embs, lit_embs)
    zs_dists     = minimal_distances_to_literature(zs_embs, lit_embs)

    static_summary = summarize_distances(static_dists)
    zs_summary     = summarize_distances(zs_dists)

    # Log summaries
    def _log(label: str, s: Dict[str, float]):
        logger.info(
            "%s → total=%.4f | avg=%.4f | min=%.4f | max=%.4f | n=%d",
            label, s["total_distance"], s["avg_distance"], s["min_distance"], s["max_distance"], s["num_drugs"]
        )

    _log("Ontology-Based (static_prompt)", static_summary)
    _log("Zero-Shot (zero_shot)", zs_summary)


    by_total = {
        "static_prompt": static_summary["total_distance"],
        "zero_shot": zs_summary["total_distance"],
    }
    closest = min(by_total, key=lambda k: by_total[k])
    logger.info("Approach closest to literature (by total distance): %s (%.4f)", closest, by_total[closest])

    # Write results table
    out_csv = os.path.join(STATS_DIR, "closest_approach_results.csv")
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "approach", "total_distance", "avg_distance", "min_distance", "max_distance", "num_drugs"
        ])
        writer.writeheader()
        writer.writerow({
            "approach": "static_prompt",
            **static_summary
        })
        writer.writerow({
            "approach": "zero_shot",
            **zs_summary
        })
    logger.info("Results table written to %s", out_csv)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())