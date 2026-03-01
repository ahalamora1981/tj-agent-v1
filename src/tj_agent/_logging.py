import sys
from pathlib import Path
from loguru import logger

logger.remove()

def format_with_color(record):
    level = record["level"].name
    msg = str(record["message"])
    # Escape < and > to avoid loguru color parsing
    msg = msg.replace("<", "\\<").replace(">", "\\>")
    if level == "INFO":
        return f"{msg}\n"
    elif level == "DEBUG":
        return f"{msg}\n"
    elif level == "WARNING":
        return f"{msg}\n"
    elif level == "ERROR":
        return f"{msg}\n"
    return f"{msg}\n"

# Console output
logger.add(sys.stderr, level="DEBUG", format=format_with_color)

# File output - full logs
log_file = Path("tj_agent.log")
logger.add(
    log_file,
    level="DEBUG",
    format="{time:HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    rotation="10 MB",
    retention="1 day"
)
