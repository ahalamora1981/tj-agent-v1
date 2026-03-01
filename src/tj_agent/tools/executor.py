from __future__ import annotations

import time
import asyncio
from typing import Any, Optional
from loguru import logger

from ..models import ToolCall, ToolResult, TOOL_REGISTRY
from .base import bash, read_file, write_file, list_directory
from .mcp import MCPClientManager


class ToolExecutor:
    """
    Executes tools and returns structured results.
    Handles both built-in tools and MCP tools.
    """
    
    def __init__(self) -> None:
        self._mcp_client = MCPClientManager.get_instance()
    
    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute a tool call and return the result.
        
        Args:
            tool_call: The tool call to execute
        
        Returns:
            ToolResult with execution outcome
        """
        start_time = time.perf_counter()
        
        logger.info(f"Executing tool: {tool_call.name}")
        
        try:
            executable = TOOL_REGISTRY.get_executable(tool_call.name)
            
            if executable is None:
                executable = self._mcp_client.get_tool(tool_call.name)
                if executable is None:
                    return ToolResult(
                        tool_call_id=tool_call.id,
                        tool_name=tool_call.name,
                        content="",
                        is_error=True,
                        error_message=f"Tool not found: {tool_call.name}",
                        execution_time_ms=int((time.perf_counter() - start_time) * 1000)
                    )
                result = await self._mcp_client.call_tool(
                    tool_call.name, 
                    tool_call.arguments
                )
                content = str(result)
            else:
                result = await self._execute_async(executable, tool_call.arguments)
                content = str(result) if result is not None else "(no output)"
            
            execution_time_ms = int((time.perf_counter() - start_time) * 1000)
            
            return ToolResult(
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                content=content,
                is_error=False,
                execution_time_ms=execution_time_ms
            )
            
        except Exception as e:
            logger.exception(f"Tool execution failed: {tool_call.name}")
            execution_time_ms = int((time.perf_counter() - start_time) * 1000)
            
            return ToolResult(
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                content="",
                is_error=True,
                error_message=str(e),
                execution_time_ms=execution_time_ms
            )
    
    async def _execute_async(
        self, 
        func: Any, 
        arguments: dict[str, Any]
    ) -> Any:
        """Execute an async function with arguments."""
        if asyncio.iscoroutinefunction(func):
            return await func(**arguments)
        return func(**arguments)


async def initialize_base_tools() -> None:
    """Initialize and register all base tools."""
    from . import base
    logger.info("Base tools initialized")
