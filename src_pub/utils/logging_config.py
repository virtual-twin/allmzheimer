"""
Logging Configuration Module
=============================

This module provides a function to set up logging configuration for the data processing pipeline.

Functions
---------
setup_logging(log_file_prefix:str="logs/pipeline", processed_file:str="")
    Set up logging configuration with a rotating file handler and stream handler.

    Parameters
    ----------
    log_file_prefix : str, optional
        Prefix for the log file path (default is "logs/pipeline").
    processed_file : str, optional
        Name of the file being processed (default is an empty string).

    Raises
    ------
    Exception
        If there is an error in setting up the logging configuration.
"""

import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
import os
import sys

def setup_logging(log_file_prefix: str = "logs/pipeline", processed_file: str = ""):
    """
    Set up logging configuration.

    Parameters
    ----------
    log_file_prefix : str
        Prefix for the log file path.
    processed_file : str
        Name of the file being processed.

    Raises
    ------
    Exception
        If there is an error in setting up the logging configuration.
    """
    try:
        # Prompt the user to enter a log level
        log_level_input = input("Enter log level (DEBUG, INFO, WARNING, ERROR, CRITICAL): ").upper()
        log_level = getattr(logging, log_level_input, logging.INFO)

        # Create a timestamp for the log file and directory structure
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        date_dir = datetime.now().strftime("%Y%m%d")

        # Create the log directory structure
        log_directory = os.path.join(log_file_prefix, date_dir)
        os.makedirs(log_directory, exist_ok=True)

        # Define the log file name
        log_file = f"{log_directory}/{processed_file}_{timestamp}.log"

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

if __name__ == "__main__":
    setup_logging()
