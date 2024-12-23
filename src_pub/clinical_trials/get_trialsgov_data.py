# Includes multithreading and neo4j acccess

import subprocess
import json
import urllib.parse
import logging
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os
import sys
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_fixed

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

# Set up logging
log_filename = "script.log"
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler(log_filename),
                              logging.StreamHandler()])

load_dotenv()
# Connection details
uri = os.getenv("uri")
username = os.getenv("username")
password = os.getenv("password")

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def fetch_studies(term, page_token=None):
    base_url = "https://clinicaltrials.gov/api/v2/studies"
    query_params = {
        "format": "json",
        "query.term": term,
        "fields": "NCTId,BriefTitle,OfficialTitle,StudyFirstPostYear,ResponsiblePartyInvestigatorAffiliation,Condition,StudyType,Phase,Sex,GenderBased,OverallStatus,Gender,EligibilityCriteria,LocationGeoPoint"
    }

    if page_token:
        query_params["pageToken"] = page_token

    query_string = urllib.parse.urlencode(query_params, safe=':@[]')
    url = f"{base_url}?{query_string}"
    
    logging.debug(f"Fetching URL: {url}")

    try:
        result = subprocess.run(
            ["curl", "-s", url],
            check=True,
            stdout=subprocess.PIPE
        )
        response = result.stdout.decode('utf-8')
        
        logging.debug(f"Raw response for term '{term}': {response}")
        
        data = json.loads(response)
        return data

    except subprocess.CalledProcessError as e:
        logging.error(f"An error occurred: {e}")
        raise
    except json.JSONDecodeError as e:
        logging.error(f"JSON decoding error: {e}")
        raise

def save_to_file(data, filename):
    with open(filename, 'w') as file:
        json.dump(data, file, indent=2)
    logging.info(f"Results saved to {filename}")

def get_drug_names_from_neo4j(uri, user, password):
    driver = GraphDatabase.driver(uri, auth=(user, password))
    query = "MATCH (n:Drug) RETURN n.name AS name"
    drug_names = []

    with driver.session() as session:
        result = session.run(query)
        for record in result:
            drug_names.append(record["name"])

    driver.close()
    return drug_names

def sanitize_filename(name):
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
            all_studies.extend(data['studies'])
            page_token = data.get('nextPageToken')
            if not page_token:
                break

        logging.info(f"Found {len(all_studies)} studies for drug: {drug_name}")

        if all_studies:
            save_to_file(all_studies, filename)
    except Exception as e:
        logging.error(f"An unexpected error occurred while processing drug '{drug_name}': {e}")

if __name__ == "__main__":
    drug_names = get_drug_names_from_neo4j(uri, username, password)
    logging.info(f"Found {len(drug_names)} drug names in the database.")

    # Create directory to save JSON files
    output_dir = "clinical_trials_data"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        logging.info(f"Created directory: {output_dir}")

    # Use ThreadPoolExecutor for multithreading
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_drug_name, drug_name, output_dir) for drug_name in drug_names]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logging.error(f"An error occurred during multithreading execution: {e}")

    logging.info(f"Processing completed.")


