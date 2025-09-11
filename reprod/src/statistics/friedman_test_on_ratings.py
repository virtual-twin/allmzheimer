import os
import sys
import logging
from typing import List

import pandas as pd
from scipy.stats import friedmanchisquare
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Project root on path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.logging_config import setup_logging


load_dotenv()

def _ensure_console_logging() -> None:
    root = logging.getLogger()
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        sh = logging.StreamHandler()
        sh.setLevel(root.level or logging.INFO)
        sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s | %(message)s"))
        root.addHandler(sh)

def _resolve_env():
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
    # 1-based indexing (rating_1..rating_N) to match integration behavior
    return [f"rating_{i}" for i in range(1, len(dirs) + 1)] or ["rating_1"]

### Friedman Test with dataframe ###

def fetch_ratings(uri, user, password, rating_properties):
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            query = f"""
                MATCH (d:Drug)
                RETURN d.name AS name, {', '.join([f'd.{prop} AS {prop}' for prop in rating_properties])}
            """
            result = session.run(query)
            data = []
            for record in result:
                row = {key: record.get(key) for key in ['name'] + rating_properties}
                data.append(row)
            return data
    except Exception as e:
        print(f"An error occurred: {e}")
        logging.exception("Error fetching ratings")
        return []
    finally:
        if 'driver' in locals():
            driver.close()

def clean_and_convert_to_numeric(data):
    df = pd.DataFrame(data)

    non_numeric_count = 0
    initial_row_count = len(df)

    rating_cols = [col for col in df.columns if col != 'name']
    for col in rating_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        non_numeric_count += df[col].isna().sum()

    dropped_drugs = df[df[rating_cols].isna().any(axis=1)]['name'].tolist()
    df_cleaned = df.dropna(subset=rating_cols)
    dropped_drugs_count = initial_row_count - len(df_cleaned)

    print(f"Number of non-numeric or missing values dropped: {non_numeric_count}")
    print(f"Number of drugs dropped due to incomplete data: {dropped_drugs_count}")
    print(f"Drugs dropped: {dropped_drugs}")

    # Ensure export dir and write cleaned matrix
    out_dir = "/app/exports/stats"
    os.makedirs(out_dir, exist_ok=True)
    out_csv = os.path.join(out_dir, "ratings_of_all_iterations_used_for_friedman_test.csv")
    df_cleaned.to_csv(out_csv, index=False)
    print(f"Cleaned data saved to '{out_csv}'")

    return df_cleaned

def perform_friedman_test(data):
    df_cleaned = clean_and_convert_to_numeric(data)

    rating_cols = [col for col in df_cleaned.columns if col != 'name']
    if len(df_cleaned) > 0 and all(len(df_cleaned[col]) == len(df_cleaned[rating_cols[0]]) for col in rating_cols):
        stat, p = friedmanchisquare(*[df_cleaned[col] for col in rating_cols])

        print(f"Friedman test statistic: {stat}")
        print(f"p-value: {p}")

        out_dir = "/app/exports/stats"
        os.makedirs(out_dir, exist_ok=True)
        out_txt = os.path.join(out_dir, "friedman_result.txt")
        with open(out_txt, "w") as f:
            f.write(f"Friedman test statistic: {stat}\n")
            f.write(f"p-value: {p}\n")
            if p < 0.05:
                f.write("Interpretation: Significant differences across iterations.\n")
            else:
                f.write("Interpretation: No strong evidence of differences across iterations.\n")
        print(f"Result written to '{out_txt}'")

        if p < 0.05:
            print("The test is significant, indicating that there is a difference in ratings across iterations.")
        else:
            print("The test is not significant, indicating no strong evidence of differences in ratings across iterations.")
    else:
        print("Not enough valid data after cleaning to perform the Friedman test.")

def main() -> int:
    setup_logging()
    _ensure_console_logging()

    try:
        dirs, uri, user, pwd = _resolve_env()
    except Exception as e:
        logging.critical("Environment resolution failed: %s", e)
        return 1

    rating_properties = _rating_properties_from_dirs(dirs)
    logging.info("Using rating properties for Friedman test: %s", rating_properties)

    data = fetch_ratings(uri, user, pwd, rating_properties)
    if data:
        perform_friedman_test(data)
    else:
        logging.warning("No rating data fetched; skipping Friedman test.")
    return 0

if __name__ == "__main__":
    sys.exit(main())