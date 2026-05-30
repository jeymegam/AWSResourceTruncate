"""Logging utilities for AWS Resource Cleanup."""

import logging
import sys
from datetime import datetime


def setup_logger(name="aws_cleanup"):
    """Configure and return a logger with console and file output."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_handler = logging.FileHandler(f"cleanup_{timestamp}.log")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
