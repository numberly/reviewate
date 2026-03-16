"""Centralized logging configuration for Reviewate.

This module provides structured logging for container-based execution.
The backend listens to these logs to track workflow status.
"""

import logging
import sys


def setup_logging(level: str = "INFO", debug: bool = False) -> None:
    """Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        debug: If True, enable DEBUG level for verbose output
    """
    effective_level = "DEBUG" if debug else level.upper()

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, effective_level))
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, effective_level))

    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Silence noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("claude_agent_sdk").setLevel(logging.WARNING)
