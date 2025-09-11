import os
import json
import logging
import re
from neo4j import GraphDatabase
from dotenv import load_dotenv
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # headless backend for Docker
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import linregress

# Load environment variables
load_dotenv()

# --- Paths (container-friendly) ---
EXPORTS_ROOT = os.getenv("EXPORTS_ROOT", "/app/exports")
TRIALS_DIR = os.getenv("CTG_DIR", os.path.join(EXPORTS_ROOT, "clinical_trials_data"))
PLOTS_DIR = os.path.join(EXPORTS_ROOT, "plots")
LOG_DIR = os.path.join("/app", "logs", "plots")
os.makedirs(PLOTS_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# Set up logging
log_filename = os.path.join(LOG_DIR, "trial_scatterplot.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_filename), logging.StreamHandler()]
)

# Critical logger (kept, but writes to container path)
critical_log_filename = os.path.join(LOG_DIR, "trial_scatterplot_critical.log")
critical_logger = logging.getLogger("critical_logger")
critical_logger.setLevel(logging.CRITICAL)
critical_handler = logging.FileHandler(critical_log_filename)
critical_logger.addHandler(critical_handler)

# Connection details
uri = os.getenv("uri")
username = os.getenv("username")
password = os.getenv("password")

# Phase mapping (unchanged semantics)
phase_mapping = {
    "NA": 0,
    "EARLY_PHASE1": 1,
    "PHASE1": 2,
    "PHASE2": 3,
    "PHASE3": 4,
    "PHASE4": 5
}

def get_drug_data_from_neo4j(uri, user, password):
    driver = GraphDatabase.driver(uri, auth=(user, password))
    query = """
    MATCH (n:Drug)
    WHERE n.rating_0 IS NOT NULL OR n.rating_1 IS NOT NULL OR n.rating_2 IS NOT NULL OR n.rating_3 IS NOT NULL
       OR n.rating_4 IS NOT NULL OR n.rating_5 IS NOT NULL OR n.rating_6 IS NOT NULL OR n.rating_7 IS NOT NULL
       OR n.rating_8 IS NOT NULL OR n.rating_9 IS NOT NULL
    RETURN n.name AS name, 
           n.rating_0 AS rating_0, n.rating_1 AS rating_1, n.rating_2 AS rating_2, n.rating_3 AS rating_3, 
           n.rating_4 AS rating_4, n.rating_5 AS rating_5, n.rating_6 AS rating_6, n.rating_7 AS rating_7, 
           n.rating_8 AS rating_8, n.rating_9 AS rating_9
    """
    drug_data = []
    non_numeric_count = 0
    try:
        with driver.session() as session:
            result = session.run(query)
            for record in result:
                ratings = []
                for i in range(10):
                    rating_value = record.get(f"rating_{i}")
                    try:
                        ratings.append(float(rating_value))
                    except (ValueError, TypeError):
                        if rating_value is not None:
                            non_numeric_count += 1
                        continue
                if ratings:
                    average_rating = sum(ratings) / len(ratings)
                    drug_data.append({"name": record["name"], "average_rating": average_rating})
    finally:
        driver.close()
    logging.info(f"Non-numeric rating values encountered and disregarded: {non_numeric_count}")
    return drug_data, non_numeric_count

def sanitize_filename(name):
    return re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "_")

def count_studies(trials_dir, drug_name):
    sanitized_name = sanitize_filename(drug_name)
    filename = os.path.join(trials_dir, f"{sanitized_name}.json")
    study_counts = {phase: 0 for phase in phase_mapping.keys()}

    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError:
                logging.warning(f"Malformed JSON for {drug_name}: {filename}")
                return study_counts
            # Each item is a study dict from ClinicalTrials.gov v2
            for trial in data:
                phases = []
                try:
                    phases = trial["protocolSection"]["designModule"].get("phases", ["NA"])
                except Exception:
                    phases = ["NA"]
                # Sometimes a single string instead of list—normalize
                if isinstance(phases, str):
                    phases = [phases]
                for phase in phases:
                    if phase in study_counts:
                        study_counts[phase] += 1
                    else:
                        # Unknown phases accrue into NA bucket
                        study_counts["NA"] += 1
    return study_counts

def create_table(drug_data):
    table_data = []
    for drug in drug_data:
        study_counts = count_studies(TRIALS_DIR, drug["name"])
        table_row = {
            "Drug": drug["name"],
            "Average Rating": drug["average_rating"],
            "Study Phase I": study_counts.get("PHASE1", 0),
            "Study Phase II": study_counts.get("PHASE2", 0),
            "Study Phase III": study_counts.get("PHASE3", 0),
            "Study Phase IV": study_counts.get("PHASE4", 0),
            "Study Phase Undefined": study_counts.get("NA", 0) + study_counts.get("EARLY_PHASE1", 0),
        }
        table_data.append(table_row)
    df = pd.DataFrame(table_data)
    return df

def log_sanity_checks(df, phases):
    for phase in phases:
        phase_data = df[["Drug", "Average Rating", phase]].sort_values(by="Average Rating", ascending=False)
        num_dots = len(phase_data[phase_data[phase] > 0])
        critical_logger.critical(f"{phase}: {num_dots} dots")
        top_3_drugs = phase_data.head(3)
        critical_logger.critical(f"Top 3 drugs in {phase} based on Average Rating:")
        critical_logger.critical("\n" + top_3_drugs.to_string(index=False))

def plot_separate_scatter_plots(df):
    phases = [
        "Study Phase I",
        "Study Phase II",
        "Study Phase III",
        "Study Phase IV",
        "Study Phase Undefined",
    ]
    colors = ["blue", "green", "orange", "purple", "grey"]

    outputs = []
    for i, phase in enumerate(phases):
        plt.figure(figsize=(10, 6))
        x = df["Average Rating"]
        y = df[phase].replace(0, np.nan)  # avoid log(0)
        log_y = np.log10(y)

        valid_idx = ~log_y.isna()
        x_valid = x[valid_idx]
        log_y_valid = log_y[valid_idx]

        plt.scatter(x_valid, log_y_valid, color=colors[i], alpha=0.7, label=f"{phase}")

        plt.title(phase, fontsize=20)
        plt.xlabel("Average Rating", fontsize=16)
        plt.ylabel("Log(Number of Studies)", fontsize=16)
        plt.xticks(fontsize={True:14, False:14}[True])
        plt.yticks(fontsize={True:14, False:14}[True])

        if len(x_valid) > 1:
            slope, intercept, r_value, p_value, std_err = linregress(x_valid, log_y_valid)
            x_fit = np.linspace(float(np.nanmin(x_valid)), float(np.nanmax(x_valid)), 500)
            y_fit = slope * x_fit + intercept

            # show regression line
            plt.plot(x_fit, y_fit, color="red", linestyle="--", linewidth=3, label="Linear Regression Line")

            # annotate R^2 and p-value
            p_value_str = "< 0.01" if p_value < 0.01 else f"{p_value:.2e}"
            textstr = r"$R^2 = \mathbf{%s}$" "\n" r"$P$-value $= \mathbf{%s}$" % (f"{r_value**2:.2f}", p_value_str)
            plt.text(
                0.05, 0.95, textstr, transform=plt.gca().transAxes,
                fontsize=16, verticalalignment="top",
                bbox=dict(facecolor="white", alpha=0.5, edgecolor="none")
            )

        plt.legend(fontsize=16, loc="upper right")
        plt.tight_layout()

        # Save instead of show (Docker/headless)
        safe_phase = phase.lower().replace(" ", "_")
        out_path = os.path.join(PLOTS_DIR, f"clinical_trials_scatter_{safe_phase}.png")
        plt.savefig(out_path, dpi=200)
        outputs.append(out_path)
        plt.close()

    logging.info("Saved phase scatter plots: %s", ", ".join(outputs))

def main():
    logging.info("Clinical-trials scatterplot: reading trials from %s", TRIALS_DIR)
    drug_data, non_numeric_count = get_drug_data_from_neo4j(uri, username, password)
    logging.info("Found %d drugs with ratings in DB.", len(drug_data))

    df = create_table(drug_data)
    logging.info("Prepared data table with shape %s", df.shape)

    print(f"Number of non-numeric rating values disregarded: {non_numeric_count}")

    log_sanity_checks(
        df,
        ["Study Phase I", "Study Phase II", "Study Phase III", "Study Phase IV", "Study Phase Undefined"]
    )
    plot_separate_scatter_plots(df)
    logging.info("Trial scatterplots written to %s", PLOTS_DIR)

if __name__ == "__main__":
    main()