from __future__ import annotations

import os
from typing import Any, Optional, AsyncIterator
import httpx
from loguru import logger

from ..models import Message, ToolDefinition, AgentConfig


class LLMClient:
    """
    Async LLM client for making API calls (OpenAI-compatible).
    Supports streaming responses.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1",
        default_model: str = "gpt-4o"
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = base_url
        self.default_model = default_model
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self) -> "LLMClient":
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=120.0
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
    
    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        tools: Optional[list[dict[str, Any]]] = None,
        stream: bool = False
    ) -> dict[str, Any] | AsyncIterator[dict[str, Any]]:
        """
        Send a chat completion request.
        
        Args:
            messages: List of message dictionaries
            model: Model to use (defaults to self.default_model)
            temperature: Sampling temperature
            tools: Tool definitions for function calling
            stream: Whether to stream the response
        
        Returns:
            Response dict or async iterator for streaming
        """
        if not self._client:
            raise RuntimeError("LLMClient must be used as async context manager")
        
        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if tools:
            payload["tools"] = tools
        
        if stream:
            payload["stream"] = True
        
        url = f"{self.base_url}/chat/completions"
        
        if stream:
            return self._stream_request(url, payload)
        
        assert self._client is not None
        response = await self._client.post(url, json=payload)
        response.raise_for_status()
        return response.json()  # type: ignore[return-value]
    
    async def _stream_request(
        self, 
        url: str, 
        payload: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        """Handle streaming response."""
        assert self._client is not None
        async with self._client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    yield {"delta": data}


class LLMClientManager:
    """Singleton manager for LLM client instances."""
    
    _instance: Optional[LLMClient] = None
    
    @classmethod
    def get_instance(
        cls, 
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None
    ) -> LLMClient:
        if cls._instance is None:
            cls._instance = LLMClient(
                api_key=api_key,
                base_url=base_url or "https://api.openai.com/v1",
                default_model=default_model or "gpt-4o"
            )
        return cls._instance
