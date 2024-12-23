# src/utils/uuid_util.py

import uuid
import logging

def generate_uuid():
    """
    Generate a unique identifier using UUID4, with extensive logging and error handling.
    
    Returns
    -------
    str
        A unique identifier string.
    
    Raises
    ------
    Exception
        If there is an error in generating the UUID.
    """
    
    try:
        logging.debug("Starting UUID generation.")
        unique_id = str(uuid.uuid4())
        logging.debug(f"Generated UUID: {unique_id}")
        return unique_id
    except Exception as e:
        logging.error(f"Failed to generate UUID: {e}")
        raise

# if __name__ == "__main__":
#     # Example usage with logging configuration for standalone testing
#     import os
#     from dotenv import load_dotenv

#     # Load environment variables & configure logging
#     def setup_environment():
#         """
#         Load environment variables and configure logging.
#         """
#         load_dotenv('.env')

#     def setup_logging():
#         """
#         Set up logging configuration.
#         """
#         log_level = logging.DEBUG
#         log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
#         logging.basicConfig(level=log_level, format=log_format)
    
#     # Setup environment and logging for standalone testing
#     setup_environment()
#     setup_logging()
    
#     # Generate a UUID to test logging
#     generate_uuid()
