from __future__ import annotations

from typing import Any, Optional, AsyncIterator
import httpx
from loguru import logger

from ..models import Message, ToolDefinition, AgentConfig
from ..llm_config import LLMConfigManager


class LLMClient:
    """Async LLM client for OpenAI-compatible API calls."""
    
    def __init__(
        self,
        api_key: str,
        base_url: str,
        default_model: str
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self) -> "LLMClient":
        self._client = httpx.AsyncClient(
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            },
            timeout=httpx.Timeout(120.0, connect=30.0)
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
    ) -> dict[str, Any] | AsyncIterator[str]:
        """Send a chat completion request."""
        if not self._client:
            raise RuntimeError("LLMClient must be used as async context manager")
        
        model = model or self.default_model
        
        payload: dict[str, Any] = {
            "model": model,
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
        
        logger.debug(f"LLM Request - URL: {url}")
        
        response = await self._client.post(url, json=payload)
        
        if response.status_code != 200:
            logger.error(f"LLM Response - Status: {response.status_code}, Body: {response.text}")
        
        response.raise_for_status()
        return response.json()
    
    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        tools: Optional[list[dict[str, Any]]] = None
    ) -> AsyncIterator[str]:
        """Send a streaming chat completion request."""
        if not self._client:
            raise RuntimeError("LLMClient must be used as async context manager")
        
        model = model or self.default_model
        
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
        
        url = f"{self.base_url}/chat/completions"
        
        logger.info(f"LLM Request: {url}")
        logger.info(f"LLM Model: {model}, Temperature: {temperature}")
        
        async for content in self._stream_request(url, payload):
            yield content
    
    async def _stream_request(
        self, 
        url: str, 
        payload: dict[str, Any]
    ) -> AsyncIterator[str]:
        """Handle streaming response, yields content chunks."""
        import json
        
        assert self._client is not None
        async with self._client.stream("POST", url, json=payload) as response:
            logger.info(f"Response status: {response.status_code}")
            
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.error(f"LLM HTTP error: {e.response.status_code} - {e.response.text}")
                raise
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    logger.debug(f"Stream data: {data[:200]}...")
                    if data == "[DONE]":
                        break
                    try:
                        chunk_data = json.loads(data)
                        choices = chunk_data.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            # Check for reasoning_content (Qwen)
                            reasoning = delta.get("reasoning_content", "")
                            if reasoning:
                                yield reasoning
                            # Check for content
                            content = delta.get("content", "")
                            if content:
                                yield content
                            # Check for tool_calls
                            tool_calls = delta.get("tool_calls", [])
                            if tool_calls:
                                # Yield tool call info
                                for tc in tool_calls:
                                    yield f"[TOOL_CALL:{tc.get('function', {}).get('name', '')}]"
                    except json.JSONDecodeError:
                        continue


class LLMClientManager:
    """Singleton manager for LLM client instances."""
    
    _instance: Optional[LLMClient] = None
    
    @classmethod
    def get_instance(
        cls,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> LLMClient:
        """Get or create LLM client with config."""
        config = LLMConfigManager.get_config(
            api_key=api_key,
            base_url=base_url,
            model=default_model,
            temperature=temperature
        )
        
        cls._instance = LLMClient(
            api_key=config.api_key,
            base_url=config.base_url,
            default_model=config.model
        )
        return cls._instance
    
    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance."""
        cls._instance = None
