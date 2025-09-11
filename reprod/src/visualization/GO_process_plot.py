# file: src/visualizations/GO_process_plot.py
import os
import logging
from collections import defaultdict
from typing import List

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from neo4j import GraphDatabase
from dotenv import load_dotenv

# ---------- Env & logging ----------
load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)

URI = os.getenv("uri")
USER = os.getenv("username")
PASSWORD = os.getenv("password")

EXPORT_DIR = os.getenv("PLOTS_EXPORT_DIR", "/app/exports/plots")
os.makedirs(EXPORT_DIR, exist_ok=True)

# ---------- Data fetch ----------
def _safe_avg(nums: List) -> float | None:
    vals: List[float] = []
    for v in nums:
        if v is None:
            continue
        try:
            vals.append(float(v))
        except (TypeError, ValueError):
            continue
    if not vals:
        return None
    return float(np.mean(vals))

def get_classification_data(uri: str, user: str, password: str):
    """
    Aggregate counts and per-class average rating.

    We consider all go_classification_0..9 per drug (if present).
    For the rating, we compute the per-drug average across rating_0..9 (numeric-only),
    and add that average once per classification occurrence for that drug.
    """
    driver = GraphDatabase.driver(uri, auth=(user, password))
    class_stats = defaultdict(lambda: {"count": 0, "total_rating": 0.0})
    non_numeric_count = 0
    row_count = 0

    # Pull everything in one pass
    cypher = """
    MATCH (d:Drug)
    RETURN
      [d.go_classification_0, d.go_classification_1, d.go_classification_2,
       d.go_classification_3, d.go_classification_4, d.go_classification_5,
       d.go_classification_6, d.go_classification_7, d.go_classification_8,
       d.go_classification_9] AS classes,
      [d.rating_0, d.rating_1, d.rating_2, d.rating_3, d.rating_4,
       d.rating_5, d.rating_6, d.rating_7, d.rating_8, d.rating_9] AS ratings
    """

    try:
        with driver.session() as session:
            result = session.run(cypher)
            for rec in result:
                row_count += 1
                classes = [c for c in rec["classes"] if c]  # keep non-null
                ratings = rec["ratings"]

                # Compute per-drug avg rating
                numeric_ratings = []
                for r in ratings:
                    if r is None:
                        continue
                    try:
                        numeric_ratings.append(float(r))
                    except (TypeError, ValueError):
                        non_numeric_count += 1
                avg_rating = float(np.mean(numeric_ratings)) if numeric_ratings else None

                if not classes:
                    continue

                for cls in classes:
                    class_stats[cls]["count"] += 1
                    if avg_rating is not None:
                        class_stats[cls]["total_rating"] += avg_rating

    finally:
        driver.close()

    logger.info("Scanned %d drugs; non-numeric rating entries encountered: %d", row_count, non_numeric_count)

    # Convert to list with avg class rating
    out = []
    for cls, d in class_stats.items():
        count = d["count"]
        total = d["total_rating"]
        class_avg = (total / count) if (count > 0 and total > 0) else (total / count if count > 0 else 0.0)
        out.append({
            "classification": cls,
            "count": count,
            "class_avg_rating": class_avg,
        })
    return out

def main() -> int:
    if not URI or not USER:
        logger.critical("Neo4j connection env not set (uri, username, password).")
        return 2

    data = get_classification_data(URI, USER, PASSWORD)
    if not data:
        logger.warning("No classification data found; nothing to plot.")
        return 0

    df = pd.DataFrame(data)
    df = df.sort_values(by="count", ascending=False).head(20)

    if df.empty:
        logger.warning("No top classifications to plot.")
        return 0

    # Truncate overly long labels for display
    def trunc(s: str, n: int = 60) -> str:
        s = s or ""
        return s if len(s) <= n else (s[: n - 3] + "...")

    df["label"] = df["classification"].apply(lambda x: trunc(str(x), 60))

    # Visualization (bubble chart)
    plt.figure(figsize=(20, 12))

    # Normalize color by avg rating (if all identical, avoid zero range)
    vmin = float(df["class_avg_rating"].min())
    vmax = float(df["class_avg_rating"].max())
    if np.isclose(vmin, vmax):
        vmax = vmin + 1e-6

    cmap = plt.colormaps.get("Purples", plt.colormaps["viridis"])
    norm = plt.Normalize(vmin=vmin, vmax=vmax)

    # y positions spaced for readability
    y_pos = np.arange(len(df)) * 8
    scatter = plt.scatter(
        df["count"].values,
        y_pos,
        s=(df["count"].values.astype(float) * 20.0),
        c=df["class_avg_rating"].values.astype(float),
        cmap=cmap,
        norm=norm,
        alpha=0.7,
        edgecolors="none",
    )

    plt.yticks(y_pos, df["label"], fontsize=12)
    plt.xlabel("Count", fontsize=14)
    plt.ylabel("GO Classification", fontsize=14)
    plt.title("Top 20 GO Processes (by count) with Average Rating", fontsize=16)
    plt.grid(True, linestyle="--", alpha=0.3)
    cbar = plt.colorbar(scatter, label="Class Average Rating")
    cbar.ax.tick_params(labelsize=12)

    plt.tight_layout()

    # Save outputs
    png_path = os.path.join(EXPORT_DIR, "go_process_top20.png")
    csv_path = os.path.join(EXPORT_DIR, "go_process_top20.csv")
    plt.savefig(png_path, dpi=600, bbox_inches="tight")
    plt.close()
    df[["classification", "count", "class_avg_rating"]].to_csv(csv_path, index=False)

    logger.info("Saved plot → %s", png_path)
    logger.info("Saved data → %s", csv_path)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())