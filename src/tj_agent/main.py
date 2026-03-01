from __future__ import annotations

import os
import sys
import uvicorn
from loguru import logger


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for the application."""
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=level
    )


def main() -> None:
    """Main entry point for TJ Agent."""
    setup_logging(os.getenv("LOG_LEVEL", "INFO"))
    
    logger.info("Starting TJ Agent...")
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    
    logger.info(f"Server starting on {host}:{port}")
    
    uvicorn.run(
        "tj_agent.app:app",
        host=host,
        port=port,
        reload=os.getenv("RELOAD", "false").lower() == "true"
    )


if __name__ == "__main__":
    main()
