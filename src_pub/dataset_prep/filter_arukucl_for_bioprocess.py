"""
This script processes the ARUK-UCL-GO-terms.tsv file to filter for biological processes.

The script performs the following steps:

    1. Reads the ARUK-UCL-GO-terms.tsv file (as it can be downloaded from the GeneOntology Website)
    2. Filters the dataset for entries where the 'GO ASPECT' column is 'P' (biological processes).
    3. Saves the filtered data to a new TSV file in datasets.


Environment Variables
---------------------
input_path_arukucl : str, optional
    The path to the input TSV file. Defaults to 'datasets/ARUK-UCL-GO-terms.tsv'. 
    If you place the dataset here you do not need to specify this path.
output_path_arukucl : str
    The path to the output TSV file. Defaults to 'datasets/bioprocess_ARUK-UCL-GO-terms.tsv'.

Functions
---------
filter_for_biological_processes()
    Function that filters the ARUK-UCL-GO-terms.tsv file for biological processes. 
    It orchestrates reading, filtering, and the export of the filtered tsv to /datasets.

Logging
-------
The script uses logging to provide information about its progress and any errors encountered.

Example
-------
To run the script, simply execute it as a standalone program:
    $ python filter_arukucl_for_bio_process.py
"""


# This file is supposed to take the downloaded ARUK-UCL-GO-terms.tsv file and filter it for the biological processe GO aspect.

import sys
import os
import pandas as pd
import os
import logging

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)


from src_pub.utils.logging_config import setup_logging
from dotenv import load_dotenv



sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Environment variables - Not needed here (unless the script is used isolated from the repo) because neo4j connection is set up in utils folder
# URI = os.getenv("uri")
# USERNAME = os.getenv("username")
# PASSWORD = os.getenv("password")
# ONTOLOGY_PATH = os.getenv("ontology_path")

# Recheck relative paths here

input_path_arukucl = os.getenv('input_path_arukucl', 'datasets/ARUK-UCL-GO-terms.tsv')
output_path_arukucl = 'datasets/bioprocess_ARUK-UCL-GO-terms.tsv'


# Add immunological processes to Neo4j database based on ARUK-UCL data

### Filter TSV file for biological processes

def filter_for_biological_processes():
    '''
    Function that filters the ARUK-UCL-GO-terms.tsv file for biological processes.
    '''
    try:
        logger.info('Reading TSV from datasets/ARUK-UCL-GO-terms.tsv')
        file_path = 'datasets/ARUK-UCL-GO-terms.tsv'
        data = pd.read_csv(file_path, sep='\t')
        logger.info('Loaded data from %s', file_path)

        logger.info('Filtering dataset for biological processes appearing as P in %s', file_path)
        filtered_data = data[data['GO ASPECT'] == 'P']
        logger.info('Filtered data for biological processes')

        output_path = 'datasets/bioprocess_ARUK-UCL-GO-terms.tsv'
        logger.info('Attempting to save filtered data to %s', output_path)
        filtered_data.to_csv(output_path, sep='\t', index=False)
        logger.info('Filtered data saved to %s', output_path)
    except Exception as e:
        logger.critical(f'An error occurred: {e}')

if __name__ == '__main__':
    filter_for_biological_processes()



