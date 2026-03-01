"""
TJ Agent - ReAct-based autonomous AI agent system.

Core data structures and models for the agent system.
"""

from .models import (
    Message,
    ToolCall, 
    ToolResult,
    AgentState,
    AgentConfig,
    SkillManifest,
    Skill,
    ToolDefinition,
    ToolRegistry,
    TOOL_REGISTRY,
)
from .llm_config import LLMConfig, LLMConfigManager
from .agents import AgentTemplate, AgentLoader, GlobalAgentLoader
from .app import app

__all__ = [
    "Message",
    "ToolCall", 
    "ToolResult",
    "AgentState",
    "AgentConfig",
    "SkillManifest",
    "Skill",
    "ToolDefinition",
    "ToolRegistry",
    "TOOL_REGISTRY",
    "LLMConfig",
    "LLMConfigManager",
    "AgentTemplate",
    "AgentLoader",
    "GlobalAgentLoader",
    "app",
]
