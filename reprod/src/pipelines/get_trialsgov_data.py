import os
import sys
import re
import json
import urllib.parse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from tenacity import retry, stop_after_attempt, wait_fixed
from neo4j import GraphDatabase
from dotenv import load_dotenv


project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Basic logging (keep simple/minimal)
log_filename = "/app/logs/clinical_trials/fetch_trialsgov.log"
os.makedirs(os.path.dirname(log_filename), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(log_filename), logging.StreamHandler(sys.stdout)]
)


load_dotenv()
# Connection details with NEO4J_AUTH fallback
uri = os.getenv("uri", "bolt://neo4j:7687")
username = os.getenv("username", "neo4j")
password = os.getenv("password")
neo_auth = os.getenv("NEO4J_AUTH", "")
if not password and neo_auth.startswith("neo4j/"):
    password = neo_auth[len("neo4j/"):]

# Tunables
MAX_WORKERS = int(os.getenv("TRIALSGOV_MAX_WORKERS", "3"))
REQUEST_TIMEOUT = float(os.getenv("TRIALSGOV_TIMEOUT", "40.0"))  # seconds

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def fetch_studies(term, page_token=None):
    """
    Fetch studies from clinicaltrials.gov v2 API.
    Minimal change from original: use 'requests' instead of 'curl'.
    """
    base_url = "https://clinicaltrials.gov/api/v2/studies"
    query_params = {
        "format": "json",
        "query.term": term,
        "fields": (
            "NCTId,BriefTitle,OfficialTitle,StudyFirstPostYear,"
            "ResponsiblePartyInvestigatorAffiliation,Condition,StudyType,Phase,"
            "Sex,GenderBased,OverallStatus,Gender,EligibilityCriteria,LocationGeoPoint"
        ),
    }
    if page_token:
        query_params["pageToken"] = page_token

    url = f"{base_url}?{urllib.parse.urlencode(query_params, safe=':@[]')}"
    logging.debug(f"Fetching URL: {url}")
    r = requests.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.json()

def save_to_file(data, filename):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logging.info(f"Results saved to {filename}")

def get_drug_names_from_neo4j(uri, user, password):
    driver = GraphDatabase.driver(uri, auth=(user, password))
    query = "MATCH (n:Drug) RETURN n.name AS name"
    drug_names = []
    try:
        with driver.session() as session:
            for record in session.run(query):
                name = record["name"]
                if isinstance(name, str) and name.strip():
                    drug_names.append(name.strip())
    finally:
        driver.close()
    return drug_names

def sanitize_filename(name):
    # Keep behavior: alnum/underscore/hyphen; spaces -> underscores
    return re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')

def process_drug_name(drug_name, output_dir):
    sanitized_name = sanitize_filename(drug_name)
    filename = os.path.join(output_dir, f"{sanitized_name}.json")

    if os.path.exists(filename):
        logging.info(f"Skipping already processed drug: {drug_name}")
        return

    logging.info(f"Fetching studies for drug: {drug_name}")
    page_token = None
    all_studies = []

    try:
        while True:
            data = fetch_studies(drug_name, page_token)
            if not data or 'studies' not in data:
                break
            all_studies.extend(data.get('studies', []))
            page_token = data.get('nextPageToken')
            if not page_token:
                break

        logging.info(f"Found {len(all_studies)} studies for drug: {drug_name}")

        if all_studies:
            save_to_file(all_studies, filename)
    except Exception as e:
        logging.error(f"Error while processing '{drug_name}': {e}")

def main():
    # Pull all drug names from DB
    drug_names = get_drug_names_from_neo4j(uri, username, password)
    logging.info(f"Found {len(drug_names)} drug names in the database.")

    # Output directory inside container (bind-mounted for visibility)
    output_dir = "/app/exports/clinical_trials_data"
    os.makedirs(output_dir, exist_ok=True)
    logging.info(f"Output directory: {output_dir}")

    # Multithreading (unchanged behavior)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(process_drug_name, dn, output_dir) for dn in drug_names]
        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception as e:
                logging.error(f"Unexpected error in worker: {e}")

    logging.info("Processing completed.")

if __name__ == "__main__":
    main()