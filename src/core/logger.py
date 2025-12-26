import logging
import sys
from rich.logging import RichHandler
from .config import settings

def setup_logger(name: str = "nexus") -> logging.Logger:
    """
    Configure and return a logger instance with Rich formatting.
    """
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(settings.LOG_LEVEL)
        
        # Console Handler with Rich
        console_handler = RichHandler(
            rich_tracebacks=True,
            markup=True,
            show_time=True,
            show_path=False
        )
        console_handler.setLevel(settings.LOG_LEVEL)
        formatter = logging.Formatter("%(message)s")
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File Handler (Optional, can be added if needed)
        # file_handler = logging.FileHandler(settings.LOGS_DIR / "app.log")
        # ...
        
    return logger

logger = setup_logger()
