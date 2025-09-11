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
# file: src/utils/logging_config.py
import logging
import os
from typing import Optional

_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}

def setup_logging(
    level: Optional[str] = None,
    *,
    fmt: str = "%(asctime)s %(levelname)s %(name)s | %(message)s",
    datefmt: Optional[str] = None,
    propagate: bool = False,
) -> None:
    """
    Non-interactive logging setup suitable for containers and CI.

    Priority:
      1) explicit `level` arg if provided
      2) env LOG_LEVEL (DEBUG|INFO|WARNING|ERROR|CRITICAL)
      3) default INFO
    """
    level_str = (level or os.getenv("LOG_LEVEL", "INFO")).upper().strip()
    log_level = _LEVELS.get(level_str, logging.INFO)

    # Configure root logger once.
    logging.basicConfig(level=log_level, format=fmt, datefmt=datefmt)
    logging.getLogger().setLevel(log_level)

    # Optional: silence overly-chatty libs if desired
    for noisy in ("neo4j", "urllib3"):
        logging.getLogger(noisy).propagate = propagate