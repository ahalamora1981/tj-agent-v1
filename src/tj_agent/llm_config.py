from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass
from loguru import logger

from dotenv import load_dotenv

_env_loaded = False

def _load_env():
    global _env_loaded
    if _env_loaded:
        return
    
    from . import _logging
    
    env_paths = [
        Path(".env"),
        Path(__file__).parent.parent / ".env",
    ]
    
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"Loaded env from {env_path}")
            break
    
    _env_loaded = True


def get_api_key() -> str:
    _load_env()
    return os.getenv("API_KEY", "")

def get_base_url() -> str:
    _load_env()
    return os.getenv("BASE_URL", "")

def get_model() -> str:
    _load_env()
    return os.getenv("MODEL", "")

def get_temperature() -> float:
    _load_env()
    return float(os.getenv("TEMPERATURE", "0.7"))


@dataclass
class LLMConfig:
    api_key: str
    base_url: str
    model: str
    temperature: float = 0.7

    def to_dict(self) -> dict[str, Any]:
        return {
            "api_key": self.api_key,
            "base_url": self.base_url,
            "model": self.model,
            "temperature": self.temperature,
        }


class LLMConfigManager:
    @classmethod
    def get_config(
        cls,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> LLMConfig:
        actual_api_key = api_key or get_api_key()
        actual_base_url = base_url or get_base_url()
        actual_model = model or get_model()
        actual_temp = temperature if temperature is not None else get_temperature()
        
        return LLMConfig(
            api_key=actual_api_key,
            base_url=actual_base_url,
            model=actual_model,
            temperature=actual_temp
        )
