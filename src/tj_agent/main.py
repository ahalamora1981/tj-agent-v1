from __future__ import annotations

import os
import sys
import uvicorn

from . import _logging  # Configure logger first
from loguru import logger


def main() -> None:
    """Main entry point for TJ Agent."""
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
