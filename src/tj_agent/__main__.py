from __future__ import annotations

import asyncio
import os
import sys
import click

from . import _logging  # Configure logger first
from loguru import logger


@click.group()
def cli():
    """TJ Agent - Interactive AI Assistant CLI."""
    pass


@cli.command()
@click.option("--agent-id", required=True, help="Agent ID to use")
def chat(agent_id: str):
    """Start interactive chat with an agent."""
    async def run():
        from .cli import TerminalClient
        client = TerminalClient(agent_id)
        if await client.initialize():
            await client.chat()
    
    asyncio.run(run())


@cli.command()
@click.option("--agent-id", required=True, help="Agent ID to use")
@click.option("--message", required=True, help="Message to send")
def run(agent_id: str, message: str):
    """Run a single message with an agent."""
    async def run_single():
        from .cli import TerminalClient
        client = TerminalClient(agent_id)
        if await client.initialize():
            response = await client.run_single(message)
            print(response)
    
    asyncio.run(run_single())


@cli.command()
def list():
    """List all available agents."""
    async def list_agents():
        from .cli import list_agents_cli
        await list_agents_cli()
    
    asyncio.run(list_agents())


@cli.command()
@click.option("--agent-id", help="Filter by agent ID")
def sessions(agent_id: str):
    """List all sessions."""
    async def list_sessions():
        from .cli import list_sessions_cli
        await list_sessions_cli(agent_id)
    
    asyncio.run(list_sessions())


@cli.command()
@click.option("--session-id", required=True, help="Session ID to delete")
def clear(session_id: str):
    """Delete a session."""
    async def clear_session():
        from .cli import clear_session_cli
        await clear_session_cli(session_id)
    
    asyncio.run(clear_session())


@cli.command()
def config():
    """Show LLM configuration."""
    async def show_config():
        from .cli import show_config_cli
        await show_config_cli()
    
    asyncio.run(show_config())


@cli.command()
def serve():
    """Start the TJ Agent API server."""
    import uvicorn
    from .app import app
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    
    logger.info(f"Starting TJ Agent server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
