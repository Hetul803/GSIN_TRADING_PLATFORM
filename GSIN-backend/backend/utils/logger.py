# backend/utils/logger.py
"""
Enhanced logging utility with structured logging support.
"""
import logging
import sys
from datetime import datetime
from typing import Optional, Dict, Any
import json

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("gsin")


def log(msg: str, level: str = "INFO") -> None:
    """
    Log a message with timestamp and level.
    
    Args:
        msg: Message to log
        level: Log level (INFO, WARNING, ERROR, DEBUG)
    """
    level_upper = level.upper()
    if level_upper == "DEBUG":
        logger.debug(f"[GSIN] {msg}")
    elif level_upper == "WARNING" or level_upper == "WARN":
        logger.warning(f"[GSIN] {msg}")
    elif level_upper == "ERROR":
        logger.error(f"[GSIN] {msg}")
    else:
        logger.info(f"[GSIN] {msg}")


def log_error(msg: str, exc_info: bool = False) -> None:
    """Log an error message."""
    logger.error(f"[GSIN] {msg}", exc_info=exc_info)


def log_warning(msg: str) -> None:
    """Log a warning message."""
    logger.warning(f"[GSIN] {msg}")


def log_info(msg: str) -> None:
    """Log an info message."""
    logger.info(f"[GSIN] {msg}")


def log_debug(msg: str) -> None:
    """Log a debug message."""
    logger.debug(f"[GSIN] {msg}")


def log_structured(event: str, data: Optional[Dict[str, Any]] = None, level: str = "INFO") -> None:
    """
    Log structured data (useful for monitoring and analytics).
    
    Args:
        event: Event name (e.g., "strategy_created", "trade_executed")
        data: Additional data to log
        level: Log level
    """
    log_data = {
        "event": event,
        "timestamp": datetime.utcnow().isoformat(),
        **{k: v for k, v in (data or {}).items() if v is not None}
    }
    
    message = json.dumps(log_data)
    
    if level.upper() == "ERROR":
        logger.error(message)
    elif level.upper() == "WARNING":
        logger.warning(message)
    elif level.upper() == "DEBUG":
        logger.debug(message)
    else:
        logger.info(message)
