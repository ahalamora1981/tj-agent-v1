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
from .memory.store import MemoryManager
from .tools import initialize_base_tools, TOOL_REGISTRY


class AgentRequest(BaseModel):
    """Request model for agent execution."""
    message: str = Field(..., description="User message to send to the agent")
    session_id: Optional[str] = Field(None, description="Session ID (auto-generated if not provided)")
    model: Optional[str] = Field(None, description="LLM model to use")
    temperature: Optional[float] = Field(0.7, description="LLM temperature")
    skills_dir: Optional[str] = Field(None, description="Path to skills directory")


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting TJ Agent...")
    
    await initialize_base_tools()
    
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
        skills_count=len(GlobalSkillLoader.get_instance().list_skill_names())
    )


@app.post("/agent", response_model=AgentResponse)
async def run_agent(request: AgentRequest):
    """Run the agent with a user message."""
    session_id = request.session_id or str(uuid.uuid4())
    
    config = AgentConfig(
        session_id=session_id,
        model=request.model or os.getenv("LLM_MODEL", "gpt-4o"),
        temperature=request.temperature or 0.7
    )
    
    runner = ReActRunner(config)
    
    try:
        response = await runner.run(request.message)
        
        return AgentResponse(
            session_id=session_id,
            response=response,
            iterations=0
        )
    except Exception as e:
        logger.exception(f"Agent execution failed: {session_id}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agent/stream")
async def run_agent_stream(request: AgentRequest):
    """Run the agent with streaming response."""
    session_id = request.session_id or str(uuid.uuid4())
    
    config = AgentConfig(
        session_id=session_id,
        model=request.model or os.getenv("LLM_MODEL", "gpt-4o"),
        temperature=request.temperature or 0.7
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
