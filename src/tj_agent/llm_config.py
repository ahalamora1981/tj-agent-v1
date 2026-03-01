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

_load_env()


LLM_PROVIDER_ENVS = {
    "openai": {
        "api_key": "OPENAI_API_KEY",
        "base_url": "OPENAI_BASE_URL",
        "default_model": "OPENAI_MODEL",
    },
    "glm": {
        "api_key": "GLM_API_KEY",
        "base_url": "GLM_BASE_URL",
        "default_model": "GLM_MODEL",
    },
    "qwen": {
        "api_key": "QWEN_API_KEY",
        "base_url": "QWEN_BASE_URL",
        "default_model": "QWEN_MODEL",
    },
    "anthropic": {
        "api_key": "ANTHROPIC_API_KEY",
        "base_url": "ANTHROPIC_BASE_URL",
        "default_model": "ANTHROPIC_MODEL",
    },
    "azure": {
        "api_key": "AZURE_OPENAI_API_KEY",
        "base_url": "AZURE_OPENAI_ENDPOINT",
        "default_model": "AZURE_OPENAI_DEPLOYMENT",
    },
    "ollama": {
        "api_key": None,
        "base_url": "OLLAMA_BASE_URL",
        "default_model": "OLLAMA_MODEL",
    },
}

DEFAULT_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "openai")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o")
DEFAULT_TEMPERATURE = float(os.getenv("DEFAULT_TEMPERATURE", "0.7"))


MODEL_TO_PROVIDER = {
    "glm-4": "glm",
    "glm-4-flash": "glm",
    "glm-4.7-flash": "glm",
    "glm-4-plus": "glm",
    "glm-3-turbo": "glm",
    "qwen": "qwen",
    "qwen-turbo": "qwen",
    "qwen-plus": "qwen",
    "qwen-max": "qwen",
    "qwen3.5": "qwen",
    "qwen3.5-flash": "qwen",
    "claude": "anthropic",
    "gpt-": "openai",
}


@dataclass
class LLMConfig:
    """LLM Provider configuration."""
    provider: str
    api_key: str
    base_url: str
    model: str
    temperature: float = 0.7

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "api_key": self.api_key,
            "base_url": self.base_url,
            "model": self.model,
            "temperature": self.temperature,
        }


class LLMConfigManager:
    """Manages LLM provider configurations from environment variables."""
    
    _configs: dict[str, LLMConfig] = {}
    
    @classmethod
    def get_config(
        cls,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> LLMConfig:
        """
        Get LLM config with fallback to environment variables.
        
        Priority: explicit params > environment variables > defaults
        """
        if not provider and model:
            for prefix, p in MODEL_TO_PROVIDER.items():
                if model.lower().startswith(prefix) or prefix in model.lower():
                    provider = p
                    break
        
        provider = provider or DEFAULT_PROVIDER
        envs = LLM_PROVIDER_ENVS.get(provider, LLM_PROVIDER_ENVS["openai"])
        
        actual_api_key = api_key
        if not actual_api_key and envs.get("api_key"):
            actual_api_key = os.getenv(envs["api_key"], "")
        
        actual_base_url = base_url
        if not actual_base_url:
            env_base_url = envs.get("base_url")
            if env_base_url:
                actual_base_url = os.getenv(env_base_url, "")
        
        actual_model = model or os.getenv(envs.get("default_model", ""), "") or DEFAULT_MODEL
        actual_temp = temperature if temperature is not None else DEFAULT_TEMPERATURE
        
        return LLMConfig(
            provider=provider,
            api_key=actual_api_key or "",
            base_url=actual_base_url or "",
            model=actual_model,
            temperature=actual_temp
        )
    
    @classmethod
    def list_providers(cls) -> list[str]:
        """List all configured providers."""
        configured = []
        for provider, envs in LLM_PROVIDER_ENVS.items():
            if envs.get("api_key"):
                api_key = os.getenv(envs["api_key"], "")
                if api_key:
                    configured.append(provider)
            elif envs.get("base_url"):
                base_url = os.getenv(envs["base_url"], "")
                if base_url:
                    configured.append(provider)
        return configured
    
    @classmethod
    def get_provider_info(cls, provider: str) -> dict[str, str]:
        """Get provider info (masked API key) for display."""
        config = cls.get_config(provider)
        masked_key = config.api_key[:8] + "***" if config.api_key else ""
        return {
            "provider": provider,
            "api_key": masked_key,
            "base_url": config.base_url,
            "model": config.model,
        }
