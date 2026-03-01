from __future__ import annotations

import os
from typing import Any, Optional, AsyncIterator
import httpx
from loguru import logger

from ..models import Message, ToolDefinition, AgentConfig
from ..llm_config import LLMConfigManager, DEFAULT_PROVIDER


class LLMClient:
    """
    Async LLM client for making API calls (OpenAI-compatible).
    Supports multiple providers: OpenAI, GLM, Qwen, Anthropic, Ollama, Azure.
    """
    
    PROVIDER_ENDPOINTS = {
        "openai": "/chat/completions",
        "glm": "/chat/completions",
        "qwen": "/chat/completions",
        "anthropic": "/v1/messages",
        "azure": "/openai/deployments/{deployment}/chat/completions",
        "ollama": "/api/chat",
    }
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1",
        default_model: str = "gpt-4o",
        provider: str = "openai"
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.provider = provider
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self) -> "LLMClient":
        self._client = httpx.AsyncClient(
            headers=self._get_headers(),
            timeout=httpx.Timeout(120.0, connect=30.0)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
    
    def _get_headers(self) -> dict[str, str]:
        """Get request headers based on provider."""
        headers = {"Content-Type": "application/json"}
        
        if self.provider == "anthropic":
            headers["x-api-key"] = self.api_key
            headers["anthropic-version"] = "2023-06-01"
        elif self.provider == "ollama":
            pass
        else:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        return headers
    
    def _get_endpoint(self) -> str:
        """Get the API endpoint path for the provider."""
        endpoint = self.PROVIDER_ENDPOINTS.get(self.provider, "/chat/completions")
        
        if self.provider == "azure":
            deployment = self.default_model
            endpoint = endpoint.replace("{deployment}", deployment)
        
        return endpoint
    
    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        tools: Optional[list[dict[str, Any]]] = None,
        stream: bool = False
    ) -> dict[str, Any] | AsyncIterator[str]:
        """
        Send a chat completion request.
        
        Args:
            messages: List of message dictionaries
            model: Model to use (defaults to self.default_model)
            temperature: Sampling temperature
            tools: Tool definitions for function calling
            stream: Whether to stream the response
        
        Returns:
            Response dict (if stream=False) or async iterator of content chunks (if stream=True)
        """
        if not self._client:
            raise RuntimeError("LLMClient must be used as async context manager")
        
        model = model or self.default_model
        
        payload: dict[str, Any] = self._build_payload(model, temperature, messages, tools, stream)
        
        endpoint = self._get_endpoint()
        url = f"{self.base_url}{endpoint}"
        
        if stream:
            return self._stream_request(url, payload)  # type: ignore[return-value]
        
        assert self._client is not None
        
        logger.debug(f"LLM Request - URL: {url}")
        logger.debug(f"LLM Request - Payload: {payload}")
        
        response = await self._client.post(url, json=payload)
        
        if response.status_code != 200:
            logger.error(f"LLM Response - Status: {response.status_code}, Body: {response.text}")
        
        response.raise_for_status()
        return self._parse_response(response.json(), stream=False)
    
    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        tools: Optional[list[dict[str, Any]]] = None
    ) -> AsyncIterator[str]:
        """
        Send a streaming chat completion request.
        
        Yields content chunks as they arrive.
        """
        if not self._client:
            raise RuntimeError("LLMClient must be used as async context manager")
        
        model = model or self.default_model
        
        payload = self._build_payload(model, temperature, messages, tools, stream=True)
        
        endpoint = self._get_endpoint()
        url = f"{self.base_url}{endpoint}"
        
        logger.debug(f"LLM Stream Request - URL: {url}")
        
        async for content in self._stream_request(url, payload):
            yield content
    
    def _build_payload(
        self,
        model: str,
        temperature: float,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]],
        stream: bool
    ) -> dict[str, Any]:
        """Build request payload based on provider."""
        if self.provider == "anthropic":
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": 4096,
                "temperature": temperature,
            }
        elif self.provider == "ollama":
            payload = {
                "model": model,
                "messages": messages,
                "stream": stream,
            }
        else:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }
            if tools:
                payload["tools"] = tools
        
        if stream:
            payload["stream"] = True
        
        return payload
    
    def _parse_response(self, response: dict[str, Any], stream: bool = False) -> dict[str, Any]:
        """Parse response based on provider format."""
        if self.provider == "anthropic":
            content = response.get("content", [])
            if isinstance(content, list) and content:
                text = "".join([c.get("text", "") for c in content if c.get("type") == "text"])
            else:
                text = str(content)
            
            return {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": text
                    }
                }]
            }
        
        return response
    
    async def _stream_request(
        self, 
        url: str, 
        payload: dict[str, Any]
    ) -> AsyncIterator[str]:
        """Handle streaming response, yields content chunks."""
        import json
        
        assert self._client is not None
        async with self._client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk_data = json.loads(data)
                        if self.provider == "anthropic":
                            content = chunk_data.get("content", [])
                            if content and isinstance(content, list):
                                for c in content:
                                    if c.get("type") == "text":
                                        yield c.get("text", "")
                        else:
                            choices = chunk_data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                    except json.JSONDecodeError:
                        continue


class LLMClientManager:
    """Singleton manager for LLM client instances."""
    
    _instance: Optional[LLMClient] = None
    
    @classmethod
    def get_instance(
        cls,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> LLMClient:
        """Get or create LLM client with config."""
        config = LLMConfigManager.get_config(
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            model=default_model,
            temperature=temperature
        )
        
        cls._instance = LLMClient(
            api_key=config.api_key,
            base_url=config.base_url,
            default_model=config.model,
            provider=config.provider
        )
        return cls._instance
    
    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance."""
        cls._instance = None
