import os
import sys
import csv
import logging
from typing import List, Tuple

from neo4j import GraphDatabase
from dotenv import load_dotenv


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.logging_config import setup_logging

# ---- Setup ----
load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

EXPORT_DIR = os.getenv("TOP100_EXPORT_DIR", "/app/exports/top_100_drugs_for_umap_plot")

# Neo4j creds
URI = os.getenv("uri")
USER = os.getenv("username")
PASSWORD = os.getenv("password")

def _safe_sum(values: List) -> Tuple[float, int]:
    """Sum numeric values, ignoring None/non-numeric. Return (sum, count_nonnull)."""
    total = 0.0
    n = 0
    for v in values or []:
        if v is None:
            continue
        try:
            total += float(v)
            n += 1
        except (TypeError, ValueError):
            continue
    return total, n

def _export_csv(rows: List[dict], out_path: str) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fieldnames = ["name", "total_rating", "num_nonnull_ratings"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    logger.info("Wrote %d rows to %s", len(rows), out_path)

def main() -> int:
    logger.info("Generating top lists for static and zero-shot ratings (sum across iterations 0..9).")
    try:
        driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
        with driver.session() as session:
            query = """
            MATCH (d:Drug)
            RETURN d.name AS name,
                   [d.rating_0, d.rating_1, d.rating_2, d.rating_3, d.rating_4,
                    d.rating_5, d.rating_6, d.rating_7, d.rating_8, d.rating_9] AS ratings,
                   [d.zero_shot_rating_0, d.zero_shot_rating_1, d.zero_shot_rating_2, d.zero_shot_rating_3, d.zero_shot_rating_4,
                    d.zero_shot_rating_5, d.zero_shot_rating_6, d.zero_shot_rating_7, d.zero_shot_rating_8, d.zero_shot_rating_9] AS zs_ratings
            """
            result = session.run(query)

            static_rows = []
            zs_rows = []
            total_nodes = 0

            for rec in result:
                total_nodes += 1
                name = rec.get("name")
                if not name:
                    continue

                s_total, s_n = _safe_sum(rec.get("ratings"))
                if s_n > 0:
                    static_rows.append({
                        "name": name,
                        "total_rating": s_total,
                        "num_nonnull_ratings": s_n
                    })

                z_total, z_n = _safe_sum(rec.get("zs_ratings"))
                if z_n > 0:
                    zs_rows.append({
                        "name": name,
                        "total_rating": z_total,
                        "num_nonnull_ratings": z_n
                    })

            logger.info("Processed %d Drug nodes. Eligible (static=%d, zero_shot=%d).",
                        total_nodes, len(static_rows), len(zs_rows))

        # Sort
        static_rows.sort(key=lambda r: r["total_rating"], reverse=True)
        zs_rows.sort(key=lambda r: r["total_rating"], reverse=True)

        # Top-100
        top_static_100 = static_rows[:100]
        top_zs_100     = zs_rows[:100]

        # Top-30
        top_static_30 = static_rows[:30]
        top_zs_30     = zs_rows[:30]

        # Export (Top-100)
        out_static_100 = os.path.join(EXPORT_DIR, "ontological_prompt_top_100.csv")
        out_zs_100     = os.path.join(EXPORT_DIR, "zero_shot_top_100.csv")
        _export_csv(top_static_100, out_static_100)
        _export_csv(top_zs_100, out_zs_100)

        # Export (Top-30)
        out_static_30 = os.path.join(EXPORT_DIR, "ontological_prompt_top_30.csv")
        out_zs_30     = os.path.join(EXPORT_DIR, "zero_shot_top_30.csv")
        _export_csv(top_static_30, out_static_30)
        _export_csv(top_zs_30, out_zs_30)

        logger.info("Top-100 and Top-30 exports complete.")
        return 0

    except Exception as e:
        logger.error("Top-list generation failed: %s", e)
        return 1

if __name__ == "__main__":
    sys.exit(main())