import os
import sys
import logging
from typing import List

import pandas as pd
from neo4j import GraphDatabase
from dotenv import load_dotenv


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.logging_config import setup_logging


logger = logging.getLogger(__name__)

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
    pwd = os.getenv("password")
    neo_auth = os.getenv("NEO4J_AUTH", "")
    if not pwd and neo_auth.startswith("neo4j/"):
        pwd = neo_auth[len("neo4j/"):]
    if not pwd:
        raise RuntimeError("Neo4j password not provided via 'password' or 'NEO4J_AUTH'.")

    return dirs, uri, user, pwd

def _rating_properties_from_dirs(dirs: List[str]) -> List[str]:
    # 1-based indexing to match integration step
    return [f"rating_{i}" for i in range(1, len(dirs) + 1)] or ["rating_1"]

def _reason_properties_from_dirs(dirs: List[str]) -> List[str]:
    return [f"reason_rating_{i}" for i in range(1, len(dirs) + 1)] or ["reason_rating_1"]

def fetch_top_rated_nodes(uri, user, password, rating_properties, reason_properties, top_n=20):
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            # Build WHERE conditions: all selected ratings must be present and numeric
            ratings_conditions = " AND ".join(
                [f"d.{prop} IS NOT NULL AND toFloat(d.{prop}) IS NOT NULL" for prop in rating_properties]
            )
            average_rating_expr = " + ".join([f"toFloat(d.{prop})" for prop in rating_properties])
            num_ratings = len(rating_properties)

            # Dynamic RETURN fields
            return_fields = [
                "d.name AS name",
                *(f"d.{rp} AS {rp}" for rp in reason_properties),
                *(f"d.{rp} AS {rp}" for rp in rating_properties),
                "d.pharmacodynamics AS pharmacodynamics",
                "d.mechanismOfAction AS mechanismOfAction",
                "d.indication AS indication",
                "d.therapeuticallySignificant AS therapeuticallySignificant",
                "d.clinicalDescription AS clinicalDescription",
                "average_rating"
            ]
            cypher = f"""
                MATCH (d:Drug)
                WHERE {ratings_conditions}
                WITH d, ({average_rating_expr}) / {num_ratings} AS average_rating
                RETURN {", ".join(return_fields)}
                ORDER BY average_rating DESC
                LIMIT {top_n}
            """

            result = session.run(cypher)
            nodes = []

            for record in result:
                row = {
                    'name': record.get('name'),
                    'average_rating': record.get('average_rating'),
                    # reasons (dynamic)
                    **{rp: record.get(rp) for rp in reason_properties},
                    # ratings (dynamic)
                    **{rp: record.get(rp) for rp in rating_properties},
                    'pharmacodynamics': record.get('pharmacodynamics'),
                    'mechanismOfAction': record.get('mechanismOfAction'),
                    'indication': record.get('indication'),
                    'therapeuticallySignificant': record.get('therapeuticallySignificant'),
                    'clinicalDescription': record.get('clinicalDescription'),
                }
                nodes.append(row)

            return nodes

    except Exception as e:
        logger.error(f"An error occurred while fetching top-rated nodes: {str(e)}")
        return []
    finally:
        if 'driver' in locals():
            driver.close()

def export_to_csv(nodes, output_file, rating_properties, reason_properties):
    desired_order = [
        'name', 'average_rating',

        *reason_properties,
        *rating_properties,
        'pharmacodynamics', 'mechanismOfAction', 'indication',
        'therapeuticallySignificant', 'clinicalDescription'
    ]
    df = pd.DataFrame(nodes)

    for col in desired_order:
        if col not in df.columns:
            df[col] = None
    df = df[desired_order]
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    df.to_csv(output_file, index=False)

def main() -> int:
    setup_logging()
    _ensure_console_logging()

    try:
        dirs, uri, user, password = _resolve_env()
    except Exception as e:
        logger.critical("Environment resolution failed: %s", e)
        return 1

    rating_properties = _rating_properties_from_dirs(dirs)
    reason_properties = _reason_properties_from_dirs(dirs)

    logger.info("Computing top rated drugs using rating properties: %s", rating_properties)

    top_rated_nodes = fetch_top_rated_nodes(uri, user, password, rating_properties, reason_properties, top_n=20)
    if top_rated_nodes:
        output_file = '/app/exports/csv/top_rated_nodes.csv'
        export_to_csv(top_rated_nodes, output_file, rating_properties, reason_properties)
        logger.info(f"Top-rated nodes exported to {output_file}")
    else:
        logger.info("No top-rated nodes found.")
    return 0

if __name__ == "__main__":
    sys.exit(main())