# file: src/pipelines/filter_arukucl_for_bio_process.py

# Filter ARUK-UCL-GO-terms.tsv for biological processes (GO ASPECT == 'P').


import sys
import os
import logging
import pandas as pd
from dotenv import load_dotenv

# basic logging setup
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

def resolve_path(p: str) -> str:
    """Return absolute path. If relative, resolve from current working dir."""
    return p if os.path.isabs(p) else os.path.abspath(os.path.join(os.getcwd(), p))

def fail(msg: str, code: int = 1):
    logger.critical(msg)
    sys.exit(code)

def filter_for_biological_processes():
    load_dotenv()  # load .env if present

    input_path = os.getenv("input_path_arukucl", "datasets/ARUK-UCL-GO-terms.tsv")
    output_path = os.getenv("output_path_arukucl", "datasets/bioprocess_ARUK-UCL-GO-terms.tsv")

    input_path = resolve_path(input_path)
    output_path = resolve_path(output_path)

    logger.info("Input TSV:  %s", input_path)
    logger.info("Output TSV: %s", output_path)

    if not os.path.isfile(input_path):
        fail(f"Input file not found: {input_path}")

    # Ensure output directory exists
    out_dir = os.path.dirname(output_path) or "."
    os.makedirs(out_dir, exist_ok=True)

    try:
        df = pd.read_csv(input_path, sep="\t", dtype=str)  # dtype=str for deterministic parsing
    except Exception as e:
        fail(f"Failed reading TSV ({input_path}): {e}")

    required_col = "GO ASPECT"
    if required_col not in df.columns:
        fail(f"Required column '{required_col}' not found. Columns present: {list(df.columns)}")

    filtered = df[df[required_col] == "P"]

    try:
        filtered.to_csv(output_path, sep="\t", index=False)
    except Exception as e:
        fail(f"Failed writing TSV ({output_path}): {e}")

    logger.info("Wrote %d rows to %s", len(filtered), output_path)

if __name__ == "__main__":
    filter_for_biological_processes()