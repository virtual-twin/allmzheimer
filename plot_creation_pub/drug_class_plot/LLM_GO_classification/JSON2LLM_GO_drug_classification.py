import os
import sys
import json
import logging
import requests
from logging.handlers import RotatingFileHandler
from datetime import datetime

def setup_logging():
    try:
        # Prompt the user to enter a directory name for the logs
        log_dir_name = input("Enter the directory name for logs: ")

        # Prompt the user to enter a log level
        log_level_input = input("Enter log level (DEBUG, INFO, WARNING, ERROR, CRITICAL): ").upper()
        log_level = getattr(logging, log_level_input, logging.INFO)

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
            logger.info("LLM Response:")
            logger.info(actual_response)
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
                    json.dump({"response": response}, output_file, indent=2)
                logger.info(f"Processed {filename} and saved response to {output_filepath}")
            else:
                logger.error(f"Failed to process {filename}")

if __name__ == "__main__":
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)

    # Prompt the user for input and output directories
    input_directory = input("Enter the input directory for JSON files: ")
    output_directory = input("Enter the output directory for JSON responses: ")

    if not os.path.isdir(input_directory):
        logger.error(f"Invalid input directory: {input_directory}")
        sys.exit(1)

    if not os.path.isdir(output_directory):
        logger.error(f"Invalid output directory: {output_directory}")
        sys.exit(1)

    process_json_files(input_directory, output_directory)
    logger.info("Finished processing all JSON files.")

