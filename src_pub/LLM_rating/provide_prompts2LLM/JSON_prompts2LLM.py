import os
import sys
import json
import logging
import requests
from logging.handlers import RotatingFileHandler
from datetime import datetime

def setup_logging(log_dir_name):
    try:
        

        # Create a timestamp for the log file and directory structure
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        date_dir = datetime.now().strftime("%Y%m%d")

        # Create the log directory structure
        log_directory = os.path.join(log_dir_name, date_dir)
        os.makedirs(log_directory, exist_ok=True)

        # Define the log file name
        log_file = f"{log_directory}/log_{timestamp}.log"

        handlers = [
            RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=10),
            logging.StreamHandler()
        ]

        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=handlers
        )

        # Confirm logging setup
        logging.info(f"Logging setup complete. Log level: {log_level_input}, Log file: {log_file}")
    except Exception as e:
        print(f"Failed to set up logging: {e}")
        logging.critical(f"Failed to set up logging: {e}")
        raise

def call_llm(prompt):
    url = "http://localhost:11434/api/generate"
    headers = {
        "Content-Type": "application/json"
    }

    data = {
        "model": "llama3:8b",
        "format": "json",
        "prompt": prompt,
        "stream": False,
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))

        if response.status_code == 200:
            response_text = response.text
            data = json.loads(response_text)
            actual_response = data["response"]
            logger.critical("LLM Response:")
            logger.critical(actual_response)
            return actual_response
        else:
            logger.error(f"Error: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        return None

def process_json_files(input_dir, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in os.listdir(input_dir):
        if filename.endswith(".json"):
            filepath = os.path.join(input_dir, filename)
            with open(filepath, 'r') as file:
                json_data = json.load(file)
                prompt = json_data["prompt"]
            
            response = call_llm(prompt)
            if response:
                output_filepath = os.path.join(output_dir, f"response_{filename}")
                with open(output_filepath, 'w') as output_file:
                    json.dump(response, output_file, indent=2)
                logger.info(f"Processed {filename} and saved response to {output_filepath}")
            else:
                logger.error(f"Failed to process {filename}")

if __name__ == "__main__":
    # Prompt the user for input and output directories
    input_directory = input("Enter the input directory for JSON files: ")
    base_output_directory = input("Enter the base output directory name for JSON responses: ")
    base_log_dir_name = input("Enter the base directory name for logs: ")
    start_iteration = int(input("Enter the starting iteration number: "))
    
    # Prompt the user to enter a log level
    log_level_input = input("Enter log level (DEBUG, INFO, WARNING, ERROR, CRITICAL): ").upper()
    log_level = getattr(logging, log_level_input, logging.INFO)

    # Loop for 3 iterations
    for i in range(3):
        iteration_number = start_iteration + i
        output_directory = f"{base_output_directory}_iteration_{iteration_number}"
        log_dir_name = f"{base_log_dir_name}_iteration_{iteration_number}"


        # Setup logging for each iteration
        setup_logging(log_dir_name)
        logger = logging.getLogger(__name__)

        process_json_files(input_directory, output_directory)
        logger.info(f"Finished processing all JSON files for iteration {iteration_number}.")
