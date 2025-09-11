# src/utils/uuid_util.py

import uuid
import logging

def generate_uuid():
    """
    Generate a unique identifier using UUID4.
    """
    
    try:
        logging.debug("Starting UUID generation.")
        unique_id = str(uuid.uuid4())
        logging.debug(f"Generated UUID: {unique_id}")
        return unique_id
    except Exception as e:
        logging.error(f"Failed to generate UUID: {e}")
        raise
