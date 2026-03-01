from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Literal, Optional
from datetime import datetime
from uuid import uuid4


class ToolCall(BaseModel):
    """Represents a single tool invocation request from the model."""
    id: str = Field(default_factory=lambda: f"call_{uuid4().hex[:8]}")
    name: str = Field(..., description="Tool name, e.g., 'bash', 'read_file', 'load_skill_instructions'")
    arguments: dict[str, Any] = Field(default_factory=dict, description="JSON parameters passed to the tool")

    model_config = {"frozen": False}


class ToolResult(BaseModel):
    """Result returned after tool execution."""
    tool_call_id: str = Field(..., description="ID of the ToolCall this result responds to")
    tool_name: str = Field(..., description="Name of the tool that was executed")
    content: str = Field(..., description="Tool execution result content")
    is_error: bool = Field(default=False, description="Whether the tool execution failed")
    error_message: Optional[str] = Field(default=None, description="Error details if is_error is True")
    execution_time_ms: Optional[int] = Field(default=None, description="Execution duration in milliseconds")

    model_config = {"frozen": False}


class Message(BaseModel):
    """Standard conversation message in the ReAct loop."""
    role: Literal["system", "user", "assistant", "tool"] = Field(..., description="Message sender role")
    content: Optional[str] = Field(default=None, description="Text content of the message")
    tool_calls: Optional[list[ToolCall]] = Field(default=None, description="Tool calls when role is assistant")
    tool_call_id: Optional[str] = Field(default=None, description="References the original ToolCall when role is tool")
    name: Optional[str] = Field(default=None, description="Name of the tool (for tool messages)")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"frozen": False}

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI-compatible message format for LLM API calls."""
        msg: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            msg["content"] = self.content
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": tc.arguments
                    }
                }
                for tc in self.tool_calls
            ]
        # Include tool_call_id for tool responses
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        if self.name:
            msg["name"] = self.name
        return msg


class SkillManifest(BaseModel):
    """YAML frontmatter parsed from a SKILL.md file (agentskills.io standard)."""
    name: str = Field(..., description="Skill display name")
    description: str = Field(..., description="Brief description for skill discovery")
    version: Optional[str] = Field(default=None, description="Skill version")
    author: Optional[str] = Field(default=None, description="Skill author")
    tags: list[str] = Field(default_factory=list, description="Categorization tags")
    triggers: list[str] = Field(
        default_factory=list,
        description="Keywords/patterns that should trigger this skill"
    )

    model_config = {"frozen": True}


class Skill(BaseModel):
    """Loaded skill with full content and manifest."""
    manifest: SkillManifest
    full_content: str = Field(..., description="Full SKILL.md Markdown content")
    skill_path: str = Field(..., description="Absolute path to the skill directory")
    scripts_path: Optional[str] = Field(default=None, description="Path to optional scripts/ directory")
    assets_path: Optional[str] = Field(default=None, description="Path to optional assets/ directory")

    model_config = {"frozen": True}


class AgentConfig(BaseModel):
    """Configuration for the agent instance."""
    session_id: str = Field(..., description="Unique session identifier")
    system_prompt: str = Field(
        default="You are TJ Agent, an autonomous AI assistant powered by ReAct architecture.",
        description="System-level instructions"
    )
    max_iterations: int = Field(default=50, description="Maximum ReAct loop iterations")
    llm_provider: Optional[str] = Field(default=None, description="LLM provider (glm, qwen, openai, etc.)")
    model: str = Field(default="gpt-4o", description="LLM model to use")
    temperature: float = Field(default=0.7, description="LLM temperature")
    base_tools_enabled: bool = Field(default=True, description="Enable base environment tools")
    mcp_enabled: bool = Field(default=False, description="Enable MCP server connections")

    model_config = {"frozen": False}


class AgentState(BaseModel):
    """Maintains the entire ReAct loop state for a session."""
    config: AgentConfig
    messages: list[Message] = Field(default_factory=list, description="Conversation history")
    active_skills: list[str] = Field(default_factory=list, description="Skills with fully loaded instructions")
    available_skills: dict[str, Skill] = Field(
        default_factory=dict,
        description="Discovered skills (name -> Skill object)"
    )
    iteration_count: int = Field(default=0, description="Current ReAct loop iteration")
    is_complete: bool = Field(default=False, description="Whether the agent has finished")
    last_error: Optional[str] = Field(default=None, description="Last error encountered")

    model_config = {"frozen": False}

    def add_message(self, message: Message) -> None:
        """Add a message to the conversation history."""
        self.messages.append(message)

    def add_skill(self, skill_name: str) -> None:
        """Mark a skill as actively loaded."""
        if skill_name not in self.active_skills:
            self.active_skills.append(skill_name)

    def get_context_messages(self) -> list[dict[str, Any]]:
        """Get all messages in OpenAI-compatible format for LLM API."""
        return [msg.to_openai_format() for msg in self.messages]


class ToolDefinition(BaseModel):
    """JSON Schema definition for a tool (matches OpenAI function calling format)."""
    type: Literal["function"] = Field(default="function")
    function: dict[str, Any] = Field(...)

    model_config = {"frozen": True}


class ToolRegistry:
    """Runtime registry for available tools (not a Pydantic model, but essential infrastructure)."""
    
    def __init__(self) -> None:
        self._tools: dict[str, dict[str, Any]] = {}
    
    def register(self, name: str, description: str, parameters_schema: dict[str, Any], executable) -> None:
        """Register a tool with its definition and callable implementation."""
        self._tools[name] = {
            "definition": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters_schema
                }
            },
            "executable": executable
        }
    
    def get_definition(self, name: str) -> Optional[ToolDefinition]:
        """Get the tool definition for LLM API."""
        if name not in self._tools:
            return None
        tool_data = self._tools[name]["definition"]
        return ToolDefinition(**tool_data)
    
    def get_definitions(self) -> list[ToolDefinition]:
        """Get all tool definitions."""
        return [self.get_definition(name) for name in self._tools.keys() if self.get_definition(name) is not None]
    
    def get_executable(self, name: str):
        """Get the callable executable for a tool."""
        return self._tools.get(name, {}).get("executable")
    
    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())
    
    def __contains__(self, name: str) -> bool:
        return name in self._tools


# Global tool registry instance
TOOL_REGISTRY = ToolRegistry()
