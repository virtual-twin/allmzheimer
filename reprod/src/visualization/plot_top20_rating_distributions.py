import os
import sys
import logging
from typing import List, Dict

import numpy as np
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Headless plotting for Docker
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Project root on path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.logging_config import setup_logging

def _ensure_console_logging() -> None:
    root = logging.getLogger()
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        sh = logging.StreamHandler()
        sh.setLevel(root.level or logging.INFO)
        sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s | %(message)s"))
        root.addHandler(sh)

def _resolve_env():
    load_dotenv()
    raw_dirs = os.getenv("RATINGS_DIRS", "").strip()
    parts = [p.strip() for token in raw_dirs.split(",") for p in token.split(":")]
    dirs = [p for p in parts if p]
    uri = os.getenv("uri", "bolt://neo4j:7687")
    user = os.getenv("username", "neo4j")
    pwd  = os.getenv("password")
    neo_auth = os.getenv("NEO4J_AUTH", "")
    if not pwd and neo_auth.startswith("neo4j/"):
        pwd = neo_auth[len("neo4j/"):]
    if not pwd:
        raise RuntimeError("Neo4j password not provided via 'password' or 'NEO4J_AUTH'.")
    return dirs, uri, user, pwd

def _rating_properties_from_dirs(dirs: List[str]) -> List[str]:
    return [f"rating_{i}" for i in range(1, len(dirs) + 1)] or ["rating_1"]

def truncate_name(name: str, char_limit: int = 15) -> str:
    return name if len(name or "") <= char_limit else (name or "")[:char_limit] + "..."

def fetch_ratings(uri, user, password, rating_properties) -> List[Dict]:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session() as session:
            query = f"""
                MATCH (d:Drug)
                RETURN d.name AS name, [{', '.join(['d.' + prop for prop in rating_properties])}] AS ratings
            """
            result = session.run(query)
            drug_ratings = []
            for record in result:
                name = record.get("name", "Unknown")
                ratings = record["ratings"]
                ratings = [float(r) for r in ratings if r is not None]
                if ratings:
                    mean_rating = float(np.mean(ratings))
                    drug_ratings.append({"name": name, "mean_rating": mean_rating, "ratings": ratings})
        # top 20 by mean
        top_20 = sorted(drug_ratings, key=lambda x: x["mean_rating"], reverse=True)[:20]
        logging.info("Selected top %d drugs by mean rating.", len(top_20))
        return top_20
    finally:
        driver.close()
        logging.info("Closed Neo4j driver.")

def plot_boxplots(drug_ratings, out_png, out_svg, char_limit=15):
    names = [d["name"] for d in drug_ratings]
    mean_ratings = [d["mean_rating"] for d in drug_ratings]
    data = [d["ratings"] for d in drug_ratings]

    sorted_idx = np.argsort(mean_ratings)
    names_sorted = [names[i] for i in sorted_idx]
    data_sorted = [data[i] for i in sorted_idx]

    truncated = [truncate_name(n, char_limit=char_limit) for n in names_sorted]
    x_positions = np.arange(1, len(names_sorted) + 1)

    plt.figure(figsize=(25, 10), dpi=150)
    bplot = plt.boxplot(
        data_sorted,
        positions=x_positions,
        widths=0.6,
        vert=True,
        patch_artist=True,
        showfliers=False,
        manage_ticks=False
    )

    for idx in range(len(bplot["boxes"])):
        box = bplot["boxes"][idx]
        whiskers = bplot["whiskers"][2*idx:2*idx+2]
        caps = bplot["caps"][2*idx:2*idx+2]
        median = bplot["medians"][idx]

        box.set_facecolor("#B19CD9")
        box.set_edgecolor("#703E85")
        box.set_linewidth(2)

        for w in whiskers:
            w.set_color("#4B0082")
            w.set_linewidth(1.5)

        for c in caps:
            c.set_color("#4B0082")
            c.set_linewidth(1.5)

        median.set_color("#4B0082")
        median.set_linewidth(2)

    plt.xticks(x_positions, truncated, rotation=90, ha="right", fontsize=22)
    plt.yticks(fontsize=22)
    plt.ylim(0.6, 1.0)
    plt.xlabel("Drugs", fontsize=30)
    plt.ylabel("Rating Values", fontsize=30)
    plt.title("Distribution of Top 20 Drug Ratings Across Rating Iterations", fontsize=34)
    plt.grid(True, axis="y", linestyle="--", alpha=0.7)
    plt.tight_layout()
    plt.savefig(out_png, dpi=150)
    plt.savefig(out_svg)
    logging.info("Saved plots: %s, %s", out_png, out_svg)

def main() -> int:
    setup_logging()
    _ensure_console_logging()

    try:
        dirs, uri, user, pwd = _resolve_env()
    except Exception as e:
        logging.critical("Env resolution failed: %s", e)
        return 1

    rating_properties = _rating_properties_from_dirs(dirs)
    if not rating_properties:
        logging.warning("No rating properties inferred; nothing to plot.")
        return 0

    logging.critical("=== Step 16 START: Top-20 rating distributions ===")
    logging.info("Using rating properties: %s", rating_properties)

    try:
        drug_ratings = fetch_ratings(uri, user, pwd, rating_properties)
    except Exception as e:
        logging.critical("Fetching ratings failed: %s", e)
        return 1

    if not drug_ratings:
        logging.warning("No drugs with ratings; plot will not be produced.")
        return 0

    out_dir = "/app/exports/plots"
    os.makedirs(out_dir, exist_ok=True)
    out_png = os.path.join(out_dir, "top20_rating_distributions.png")
    out_svg = os.path.join(out_dir, "top20_rating_distributions.svg")

    try:
        plot_boxplots(drug_ratings, out_png, out_svg, char_limit=15)
    except Exception as e:
        logging.critical("Plot generation failed: %s", e)
        return 1

    logging.critical("=== Step 16 END ===")
    return 0

if __name__ == "__main__":
    sys.exit(main())