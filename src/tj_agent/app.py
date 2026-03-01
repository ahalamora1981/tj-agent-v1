from __future__ import annotations

import os
import uuid
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from loguru import logger

from .models import AgentConfig
from .react import ReActRunner
from .skills import GlobalSkillLoader
from .agents import GlobalAgentLoader
from .memory.store import MemoryManager
from .llm_config import LLMConfigManager
from .tools import initialize_base_tools, TOOL_REGISTRY


class AgentRequest(BaseModel):
    """Request model for agent execution."""
    message: str = Field(..., description="User message to send to the agent")
    agent_id: str = Field(..., description="Agent ID to use")
    session_id: Optional[str] = Field(None, description="Session ID (auto-generated if not provided)")
    temperature: Optional[float] = Field(None, description="LLM temperature (overrides agent config)")


class AgentResponse(BaseModel):
    """Response model for agent execution."""
    session_id: str
    response: str
    iterations: int
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    tools_count: int
    skills_count: int
    agents_count: int


class ConfigResponse(BaseModel):
    """LLM configuration response."""
    providers: list[dict[str, str]]


class SessionListResponse(BaseModel):
    """List of sessions."""
    sessions: list[dict[str, Any]]


import typing
Any = typing.Any


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting TJ Agent...")
    
    await initialize_base_tools()
    
    agents_dir = os.getenv("AGENTS_DIR", "agents")
    if os.path.exists(agents_dir):
        count = GlobalAgentLoader.load(agents_dir)
        logger.info(f"Loaded {count} agents")
    else:
        logger.warning(f"Agents directory not found: {agents_dir}")
    
    skills_dir = os.getenv("SKILLS_DIR", "skills")
    if os.path.exists(skills_dir):
        count = await GlobalSkillLoader.discover(skills_dir)
        logger.info(f"Loaded {count} skills")
    else:
        logger.warning(f"Skills directory not found: {skills_dir}")
    
    yield
    
    await MemoryManager.close()
    logger.info("TJ Agent shut down")


app = FastAPI(
    title="TJ Agent",
    description="ReAct-based autonomous AI agent system",
    version="0.1.0",
    lifespan=lifespan
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        tools_count=len(TOOL_REGISTRY.list_tools()),
        skills_count=len(GlobalSkillLoader.get_instance().list_skill_names()),
        agents_count=len(GlobalAgentLoader.list_agents())
    )


@app.get("/config", response_model=ConfigResponse)
async def get_config():
    """Get LLM provider configurations."""
    providers = LLMConfigManager.list_providers()
    return ConfigResponse(
        providers=[LLMConfigManager.get_provider_info(p) for p in providers]
    )


@app.get("/agents", response_model=list)
async def list_agents():
    """List all available agents."""
    return GlobalAgentLoader.list_agents()


@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get agent details."""
    agent = GlobalAgentLoader.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
    return agent.to_dict()


@app.get("/sessions", response_model=SessionListResponse)
async def list_sessions(agent_id: Optional[str] = None, limit: int = 50):
    """List all sessions."""
    session_mgr = await MemoryManager.get_session_manager()
    sessions = await session_mgr.list_sessions(agent_id, limit)
    return SessionListResponse(sessions=sessions)


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session details and messages."""
    session_mgr = await MemoryManager.get_session_manager()
    session = await session_mgr.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    messages = await session_mgr.get_messages(session_id)
    return {
        "session": session,
        "messages": messages
    }


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    session_mgr = await MemoryManager.get_session_manager()
    success = await session_mgr.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return {"status": "deleted", "session_id": session_id}


@app.post("/agent", response_model=AgentResponse)
async def run_agent(request: AgentRequest):
    """Run the agent with a user message."""
    agent = GlobalAgentLoader.get_agent(request.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {request.agent_id}")
    
    session_mgr = await MemoryManager.get_session_manager()
    
    session_id = request.session_id
    if not session_id:
        session_id = await session_mgr.create_session(request.agent_id)
    
    config = AgentConfig(
        session_id=session_id,
        system_prompt=agent.system_prompt,
        model=os.getenv("MODEL") or "glm-4.7-flash",
        temperature=float(os.getenv("TEMPERATURE", "0.7"))
    )
    
    runner = ReActRunner(config)
    
    try:
        await session_mgr.add_message(session_id, "user", request.message)
        
        response = await runner.run(request.message)
        
        await session_mgr.add_message(session_id, "assistant", response)
        
        return AgentResponse(
            session_id=session_id,
            response=response,
            iterations=runner.state.iteration_count if hasattr(runner, 'state') else 0
        )
    except Exception as e:
        logger.exception(f"Agent execution failed: {session_id}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agent/stream")
async def run_agent_stream(request: AgentRequest):
    """Run the agent with streaming response."""
    agent = GlobalAgentLoader.get_agent(request.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {request.agent_id}")
    
    session_mgr = await MemoryManager.get_session_manager()
    
    session_id = request.session_id
    if not session_id:
        session_id = await session_mgr.create_session(request.agent_id)
    
    config = AgentConfig(
        session_id=session_id,
        system_prompt=agent.system_prompt,
        model=os.getenv("MODEL") or "glm-4.7-flash",
        temperature=float(os.getenv("TEMPERATURE", "0.7"))
    )
    
    runner = ReActRunner(config)
    
    async def event_generator():
        yield f"data: Session {session_id}\n\n"
        
        async for chunk in runner.run_streaming(request.message):
            yield f"data: {chunk}\n\n"
        
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


@app.get("/tools")
async def list_tools():
    """List all available tools."""
    return {
        "tools": [
            {
                "name": name,
                "definition": TOOL_REGISTRY.get_definition(name).function
            }
            for name in TOOL_REGISTRY.list_tools()
        ]
    }


@app.get("/skills")
async def list_skills():
    """List all available skills."""
    loader = GlobalSkillLoader.get_instance()
    return {
        "skills": [
            {
                "name": skill.manifest.name,
                "description": skill.manifest.description,
                "tags": skill.manifest.tags
            }
            for skill in loader.skills.values()
        ]
    }
