from __future__ import annotations

import os
import sys
import asyncio
import json
from pathlib import Path
from typing import Optional
from loguru import logger

from . import _logging  # Configure logger first
from .models import AgentConfig
from .react import ReActRunner
from .agents import GlobalAgentLoader
from .skills import GlobalSkillLoader, set_agent_state
from .memory.store import MemoryManager
from .llm_config import LLMConfigManager
from .tools import initialize_base_tools, TOOL_REGISTRY


class ExitChatException(Exception):
    """Exception to exit chat loop gracefully."""
    pass


class TerminalClient:
    """Interactive terminal client for TJ Agent."""
    
    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.agent = None
        self.session_id: Optional[str] = None
        self.runner: Optional[ReActRunner] = None
    
    async def initialize(self) -> bool:
        """Initialize the client and load agent."""
        await initialize_base_tools()
        
        agents_dir = os.getenv("AGENTS_DIR", "agents")
        GlobalAgentLoader.load(agents_dir)
        
        skills_dir = os.getenv("SKILLS_DIR", "skills")
        if os.path.exists(skills_dir):
            await GlobalSkillLoader.discover(skills_dir)
        
        self.agent = GlobalAgentLoader.get_agent(self.agent_id)
        if not self.agent:
            print(f"[错误] Agent 未找到: {self.agent_id}")
            print(f"可用的 Agents: {', '.join(a['id'] for a in GlobalAgentLoader.list_agents())}")
            return False
        
        memory = await MemoryManager.get_instance()
        session_mgr = memory.session_manager
        self.session_id = await session_mgr.create_session(self.agent_id)
        
        return True
    
    async def chat(self) -> None:
        """Start interactive chat."""
        if not self.agent or not self.session_id:
            return
        
        self._print_header()
        
        session_mgr = (await MemoryManager.get_instance()).session_manager
        messages = await session_mgr.get_messages(self.session_id)
        
        if messages:
            print("\n[历史消息]\n")
            for msg in messages:
                role_emoji = {"user": "[U]", "assistant": "[A]", "tool": "[T]"}.get(msg["role"], "[?]")
                content = msg["content"] or ""
                if len(content) > 200:
                    content = content[:200] + "..."
                print(f"{role_emoji} {msg['role']}: {content}\n")
        
        while True:
            try:
                user_input = input("\n> ")
                
                if not user_input:
                    continue
                
                if user_input.lower() == "/exit":
                    print("\nGoodbye!")
                    raise ExitChatException()
                
                if user_input.lower() == "/new":
                    session_mgr = (await MemoryManager.get_instance()).session_manager
                    self.session_id = await session_mgr.create_session(self.agent_id)
                    print(f"\n[新会话已创建: {self.session_id[:8]}...]")
                    continue
                
                if user_input.lower() == "/tools":
                    print("\n可用工具:")
                    for name in TOOL_REGISTRY.list_tools():
                        defn = TOOL_REGISTRY.get_definition(name)
                        if defn:
                            print(f"  - {name}: {defn.function.get('description', '')}")
                    print()
                    continue
                
                if user_input.lower() in ["exit", "quit", "q"]:
                    print("\nGoodbye!")
                    sys.exit(0)
                
                await session_mgr.add_message(self.session_id, "user", user_input)
                
                skills_loader = GlobalSkillLoader.get_instance()
                discovery_prompt = skills_loader.get_discovery_prompt()
                
                full_system_prompt = self.agent.system_prompt
                if discovery_prompt:
                    full_system_prompt += "\n\n" + discovery_prompt
                
                config = AgentConfig(
                    session_id=self.session_id,
                    system_prompt=full_system_prompt,
                    model=os.getenv("MODEL") or "glm-4.7-flash",
                    temperature=float(os.getenv("TEMPERATURE", "0.7"))
                )
                
                def stream_callback(chunk: str) -> None:
                    print(chunk, end="", flush=True)
                
                self.runner = ReActRunner(config, stream_callback=stream_callback)
                
                if self.runner.state:
                    set_agent_state(self.runner.state)
                
                print("\n" + "─" * 60)
                sys.stdout.flush()
                print("\n[Answer]: ", end="", flush=True)
                sys.stdout.flush()
                
                response = await self.runner.run(user_input)
                
                print()  # newline after streaming
                
                await session_mgr.add_message(self.session_id, "assistant", response)
                
                print("-" * 60)
                
            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                raise ExitChatException()
            except ExitChatException:
                try:
                    await MemoryManager.close()
                except Exception:
                    pass
                os._exit(0)
            except Exception as e:
                logger.exception("Chat error")
                print(f"\n[错误] {str(e)}")
    
    def _print_header(self) -> None:
        """Print the chat header."""
        if not self.agent:
            return
        from .llm_config import LLMConfigManager
        config = LLMConfigManager.get_config()
        print(f"""
============================================================
  {self.agent.name} ({self.agent_id})
  Model: {config.model} | URL: {config.base_url}
============================================================
""")
    
    async def run_single(self, message: str) -> str:
        """Run a single message and return response."""
        if not self.agent:
            return f"Agent not found: {self.agent_id}"
        
        session_id = self.session_id or "temp"
        
        config = AgentConfig(
            session_id=session_id,
            system_prompt=self.agent.system_prompt,
            model=os.getenv("MODEL") or "glm-4.7-flash",
            temperature=float(os.getenv("TEMPERATURE", "0.7"))
        )
        
        self.runner = ReActRunner(config)
        if self.runner.state:
            set_agent_state(self.runner.state)
        
        return await self.runner.run(message)


async def list_agents_cli() -> None:
    """List all available agents."""
    agents_dir = os.getenv("AGENTS_DIR", "agents")
    agents = GlobalAgentLoader.load(agents_dir)
    agent_list = GlobalAgentLoader.list_agents()
    
    if not agent_list:
        print("没有找到任何 Agent。请在 agents/ 目录下创建 YAML 文件。")
        return
    
    print("\n可用 Agents:\n")
    for agent in agent_list:
        print(f"  • {agent['id']}: {agent['name']}")
        print(f"    模型: {agent['model']} | 提供商: {agent['provider']}")
        print(f"    描述: {agent['description']}")
        print()


async def list_sessions_cli(agent_id: Optional[str] = None) -> None:
    """List all sessions."""
    memory = await MemoryManager.get_instance()
    session_mgr = memory.session_manager
    sessions = await session_mgr.list_sessions(agent_id)
    
    if not sessions:
        print("没有找到任何会话。")
        return
    
    print("\n会话列表:\n")
    for s in sessions:
        print(f"  • {s['id']}")
        print(f"    Agent: {s['agent_id']} | 标题: {s['title']}")
        print(f"    创建: {s['created_at']} | 更新: {s['updated_at']}")
        print()


async def clear_session_cli(session_id: str) -> None:
    """Clear a session."""
    memory = await MemoryManager.get_instance()
    session_mgr = memory.session_manager
    await session_mgr.delete_session(session_id)
    print(f"会话已删除: {session_id}")


async def show_config_cli() -> None:
    """Show LLM configuration."""
    providers = LLMConfigManager.list_providers()
    
    if not providers:
        print("没有找到已配置的 LLM Provider。请在 .env 文件中配置。")
        return
    
    print("\n已配置的 LLM Providers:\n")
    for p in providers:
        info = LLMConfigManager.get_provider_info(p)
        print(f"  • {info['provider']}")
        print(f"    API Key: {info['api_key']}")
        print(f"    Base URL: {info['base_url']}")
        print(f"    Model: {info['model']}")
        print()
