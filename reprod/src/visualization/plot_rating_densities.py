# file: src/visualization/plot_rating_densities.py
"""
Generate a density comparison plot of LLM ratings across iterations.

- Iterations are inferred from RATINGS_DIRS (.env), consumed left-to-right.
- Queries rating_1..rating_N properties from :Drug nodes.
- Saves a PNG (and SVG) and a CSV of summary statistics.

Outputs:
  /app/exports/plots/ratings_density.png
  /app/exports/plots/ratings_density.svg
  /app/exports/plots/ratings_density_stats.csv
"""

import os
import sys
import logging
from typing import List, Dict
from dotenv import load_dotenv

# Project root on path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.logging_config import setup_logging

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")  # headless rendering for Docker
import matplotlib.pyplot as plt

try:
    from scipy.stats import gaussian_kde  # optional
    HAVE_SCIPY = True
except Exception:
    HAVE_SCIPY = False

from neo4j import GraphDatabase


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
    pwd = os.getenv("password")
    neo_auth = os.getenv("NEO4J_AUTH", "")
    if not pwd and neo_auth.startswith("neo4j/"):
        pwd = neo_auth[len("neo4j/"):]
    if not pwd:
        raise RuntimeError("Neo4j password not provided via 'password' or 'NEO4J_AUTH'.")
    return dirs, uri, user, pwd


def _rating_properties_from_dirs(dirs: List[str]) -> List[str]:
    # 1-based indexing to match Step 13 behavior
    return [f"rating_{i}" for i in range(1, len(dirs) + 1)]


def _fetch_ratings(uri: str, user: str, password: str, rating_props: List[str]) -> Dict[str, List[float]]:
    ratings: Dict[str, List[float]] = {p: [] for p in rating_props}
    logging.info("Connecting to Neo4j to fetch ratings for properties: %s", rating_props)
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session() as session:
            for prop in rating_props:
                cypher = f"""
                    MATCH (d:Drug)
                    WHERE d.{prop} IS NOT NULL
                    RETURN d.{prop} AS rating
                """
                vals = []
                for rec in session.run(cypher):
                    vals.append(rec["rating"])
                ratings[prop] = vals
                logging.info("Fetched %d ratings for %s", len(vals), prop)
    finally:
        driver.close()
        logging.info("Closed Neo4j driver.")
    return ratings


def _prepare_output_dir() -> str:
    out_dir = "/app/exports/plots"
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


def _summarize_to_csv(ratings: Dict[str, List[float]], out_csv: str) -> None:
    rows = []
    for prop, vals in ratings.items():
        s = pd.to_numeric(pd.Series(vals), errors="coerce").dropna()
        if s.empty:
            rows.append({
                "property": prop, "count": 0, "mean": np.nan, "std": np.nan,
                "min": np.nan, "q25": np.nan, "median": np.nan, "q75": np.nan, "max": np.nan
            })
        else:
            rows.append({
                "property": prop,
                "count": int(s.shape[0]),
                "mean": float(s.mean()),
                "std": float(s.std(ddof=1)) if s.shape[0] > 1 else 0.0,
                "min": float(s.min()),
                "q25": float(s.quantile(0.25)),
                "median": float(s.median()),
                "q75": float(s.quantile(0.75)),
                "max": float(s.max())
            })
    df = pd.DataFrame(rows)
    df.to_csv(out_csv, index=False)
    logging.info("Wrote summary stats to %s", out_csv)


def _plot_density(ratings: Dict[str, List[float]], labels: Dict[str, str], out_png: str, out_svg: str) -> None:
    plt.figure(figsize=(12, 8))
    plotted = 0

    for prop, values in ratings.items():
        s = pd.to_numeric(pd.Series(values), errors="coerce").dropna()
        if s.empty:
            logging.warning("No numeric ratings for %s; skipping curve.", prop)
            continue

        xs = np.linspace(float(s.min()), float(s.max()), 200) if s.min() != s.max() else np.linspace(0.0, 1.0, 200)
        label = labels.get(prop, prop)

        if HAVE_SCIPY and s.nunique() > 1:
            kde = gaussian_kde(s.values)
            ys = kde(xs)
            plt.plot(xs, ys, label=label, alpha=0.9)
        else:
            # Fallback: normalized histogram line (no SciPy or all values equal)
            hist, bin_edges = np.histogram(s.values, bins=30, range=(0.0, 1.0), density=True)
            centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
            plt.plot(centers, hist, label=label, alpha=0.9)

        plotted += 1

    plt.title('Density of Drug Ratings Across Iterations')
    plt.xlabel('Rating')
    plt.ylabel('Density')
    if plotted > 0:
        plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_png, dpi=150)
    plt.savefig(out_svg)
    logging.info("Saved plots: %s and %s", out_png, out_svg)


def main() -> int:
    setup_logging()
    _ensure_console_logging()

    try:
        dirs, uri, user, pwd = _resolve_env()
    except Exception as e:
        logging.critical("Cannot resolve environment: %s", e)
        return 1

    if not dirs:
        logging.critical("RATINGS_DIRS is empty; nothing to plot.")
        return 0

    logging.critical("=== Step 14 START: Plot rating distributions ===")
    logging.info("RATINGS_DIRS has %d directories (1-based indexing): %s", len(dirs), dirs)

    rating_props = _rating_properties_from_dirs(dirs)
    custom_labels = {prop: f"Iteration {i}" for i, prop in enumerate(rating_props, start=1)}

    try:
        ratings = _fetch_ratings(uri, user, pwd, rating_props)
    except Exception as e:
        logging.critical("Failed fetching ratings: %s", e)
        return 1

    if not any(len(v) for v in ratings.values()):
        logging.warning("No ratings present in DB for %s; plot will be empty.", rating_props)

    out_dir = _prepare_output_dir()
    out_png = os.path.join(out_dir, "ratings_density.png")
    out_svg = os.path.join(out_dir, "ratings_density.svg")
    out_csv = os.path.join(out_dir, "ratings_density_stats.csv")

    try:
        _plot_density(ratings, custom_labels, out_png, out_svg)
        _summarize_to_csv(ratings, out_csv)
    except Exception as e:
        logging.critical("Failed to render/save plots or stats: %s", e)
        return 1

    logging.critical("=== Step 14 END ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())