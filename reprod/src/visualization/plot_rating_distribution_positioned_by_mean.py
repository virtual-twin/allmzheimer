import os
import sys
import logging
from typing import List

import numpy as np
import pandas as pd
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
    # allow comma or colon separators, and tolerate extra spaces
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
    # 1-based indexing to match integration step
    return [f"rating_{i}" for i in range(1, len(dirs) + 1)] or ["rating_1"]

def fetch_ratings(uri, user, password, rating_properties):
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session() as session:
            query = f"""
                MATCH (d:Drug)
                RETURN [{', '.join(['d.' + prop for prop in rating_properties])}] AS ratings
            """
            result = session.run(query)
            drug_ratings = []
            for record in result:
                ratings = record["ratings"]
                ratings = [float(r) for r in ratings if r is not None]
                if ratings:
                    mean_rating = float(np.mean(ratings))
                    drug_ratings.append({"mean_rating": mean_rating, "ratings": ratings})
            logging.info("Fetched %d drugs with at least one rating.", len(drug_ratings))
            return drug_ratings
    finally:
        driver.close()
        logging.info("Closed Neo4j driver.")

def plot_boxplots(drug_ratings, out_png, out_svg):
    mean_ratings = [drug["mean_rating"] for drug in drug_ratings]
    data = [drug["ratings"] for drug in drug_ratings]

    variability = []
    for ratings in data:
        if len(ratings) >= 2:
            q1, q3 = np.percentile(ratings, [25, 75])
            iqr = float(q3 - q1)
            variability.append(iqr)
        else:
            variability.append(0.0)

    variability = np.array(variability, dtype=float)
    vmax, vmin = variability.max(initial=0.0), variability.min(initial=0.0)
    if vmax - vmin == 0:
        variability_normalized = np.zeros_like(variability)
    else:
        variability_normalized = (variability - vmin) / (vmax - vmin)

    min_alpha, max_alpha = 0.001, 0.99
    alphas = max_alpha - variability_normalized * (max_alpha - min_alpha)

    sorted_idx = np.argsort(mean_ratings)
    mean_ratings = np.array(mean_ratings, dtype=float)[sorted_idx]
    data = [data[i] for i in sorted_idx]
    alphas = alphas[sorted_idx]

    plt.figure(figsize=(40, 15), dpi=150)
    bplot = plt.boxplot(
        data,
        positions=mean_ratings,
        widths=0.005,
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
        alpha = float(alphas[idx])

        box.set_facecolor("purple")
        box.set_alpha(alpha)
        box.set_edgecolor("black")
        for w in whiskers:
            w.set_color("black"); w.set_alpha(alpha)
        for c in caps:
            c.set_color("black"); c.set_alpha(alpha)
        median.set_color("black"); median.set_alpha(alpha)

    plt.ylim(0, 1)
    plt.xlim(0, 1)
    plt.xlabel("Average Rating of Drugs", fontsize=40)
    plt.ylabel("Rating Values", fontsize=40)
    plt.title("Distribution of Drug Ratings Positioned by Their Average Ratings", fontsize=40)
    plt.xticks(fontsize=30)
    plt.yticks(fontsize=30)
    plt.grid(True, alpha=0.3)
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

    logging.critical("=== Step 15 START: Rating distribution positioned by mean ===")
    logging.info("Using rating properties: %s", rating_properties)

    drug_ratings = fetch_ratings(uri, user, pwd, rating_properties)
    if not drug_ratings:
        logging.warning("No drugs with ratings; plot will not be produced.")
        return 0

    out_dir = "/app/exports/plots"
    os.makedirs(out_dir, exist_ok=True)
    out_png = os.path.join(out_dir, "rating_distribution_positioned_by_mean.png")
    out_svg = os.path.join(out_dir, "rating_distribution_positioned_by_mean.svg")

    try:
        plot_boxplots(drug_ratings, out_png, out_svg)
    except Exception as e:
        logging.critical("Plot generation failed: %s", e)
        return 1

    logging.critical("=== Step 15 END ===")
    return 0

if __name__ == "__main__":
    sys.exit(main())