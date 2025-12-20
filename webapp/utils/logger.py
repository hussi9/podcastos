import logging
import sys
import json
from datetime import datetime
from pathlib import Path

# Create logs directory
LOG_DIR = Path(__file__).parent.parent.parent / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)

class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "line": record.lineno,
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)

def get_logger(name: str):
    """
    Get a configured logger instance.
    Writes structured JSON logs to file and colored text logs to stdout.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Avoid adding duplicate handlers if get_logger is called multiple times
    if logger.handlers:
        return logger

    # Console Handler (Human readable)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File Handler (Structured JSON)
    file_handler = logging.FileHandler(LOG_DIR / 'podcast_studio.json.log')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(JsonFormatter())
    logger.addHandler(file_handler)

    return logger
