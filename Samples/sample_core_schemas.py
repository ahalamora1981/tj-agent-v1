# sample_core_schemas.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal

class ToolCall(BaseModel):
    """表示模型发起的一次工具调用请求"""
    id: str = Field(..., description="工具调用的唯一标识符")
    name: str = Field(..., description="要调用的工具名称，例如 'bash' 或 'load_skill_instructions'")
    arguments: Dict[str, Any] = Field(..., description="传递给工具的 JSON 格式参数")

class Message(BaseModel):
    """标准的对话消息体"""
    role: Literal["system", "user", "assistant", "tool"] = Field(...)
    content: str | None = Field(None, description="消息文本内容")
    tool_calls: Optional[List[ToolCall]] = Field(None, description="当 role 为 assistant 时，包含的工具调用请求")
    tool_call_id: Optional[str] = Field(None, description="当 role 为 tool 时，对应的问题 ID")

class AgentState(BaseModel):
    """维护整个 ReAct 循环的状态"""
    session_id: str
    messages: List[Message] = Field(default_factory=list)
    active_skills: List[str] = Field(default_factory=list, description="当前已激活(加载完全文)的 Skills")