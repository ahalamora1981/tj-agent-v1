from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from loguru import logger

from .registry import tj_tool


@tj_tool(
    name="bash",
    description="Execute a bash/shell command. Use this to run scripts, git commands, or system operations."
)
async def bash(command: str, timeout: int = 30, cwd: str | None = None) -> str:
    """
    Execute a bash command and return its output.
    
    Args:
        command: The shell command to execute
        timeout: Timeout in seconds (default 30)
        cwd: Optional working directory
    
    Returns:
        Command stdout/stderr output
    """
    logger.info(f"Executing bash: {command}")
    
    try:
        result = await asyncio.wait_for(
            asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            ),
            timeout=timeout
        )
        
        stdout, stderr = await result.communicate()
        
        output_lines = []
        if stdout:
            output_lines.append(stdout.decode("utf-8", errors="replace"))
        if stderr:
            output_lines.append(f"[STDERR] {stderr.decode('utf-8', errors='replace')}")
        
        output = "\n".join(output_lines) if output_lines else "(no output)"
        
        if result.returncode != 0:
            output = f"[Exit code: {result.returncode}]\n{output}"
        
        return output
        
    except asyncio.TimeoutError:
        return f"[ERROR] Command timed out after {timeout} seconds"
    except Exception as e:
        logger.exception(f"Bash execution failed: {command}")
        return f"[ERROR] {str(e)}"


@tj_tool(
    name="read_file",
    description="Read the contents of a file from the local filesystem."
)
async def read_file(file_path: str, encoding: str = "utf-8") -> str:
    """
    Read a file's contents.
    
    Args:
        file_path: Absolute or relative path to the file
        encoding: File encoding (default utf-8)
    
    Returns:
        File contents as string
    """
    logger.debug(f"Reading file: {file_path}")
    
    try:
        path = Path(file_path)
        if not path.exists():
            return f"[ERROR] File not found: {file_path}"
        
        content = path.read_text(encoding=encoding)
        return content
        
    except UnicodeDecodeError:
        return f"[ERROR] Failed to decode file with {encoding} encoding"
    except Exception as e:
        logger.exception(f"File read failed: {file_path}")
        return f"[ERROR] {str(e)}"


@tj_tool(
    name="write_file",
    description="Write content to a file. Creates the file if it doesn't exist."
)
async def write_file(file_path: str, content: str, encoding: str = "utf-8", append: bool = False) -> str:
    """
    Write content to a file.
    
    Args:
        file_path: Absolute or relative path to the file
        content: Content to write
        encoding: File encoding (default utf-8)
        append: If True, append to existing file; otherwise overwrite
    
    Returns:
        Success or error message
    """
    logger.debug(f"Writing file: {file_path} (append={append})")
    
    try:
        path = Path(file_path)
        
        if not append:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding=encoding)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            existing = ""
            if path.exists():
                existing = path.read_text(encoding=encoding)
            path.write_text(existing + content, encoding=encoding)
        
        return f"[OK] Written to {file_path}"
        
    except Exception as e:
        logger.exception(f"File write failed: {file_path}")
        return f"[ERROR] {str(e)}"


@tj_tool(
    name="list_directory",
    description="List files and directories in a given path."
)
async def list_directory(path: str = ".", include_hidden: bool = False) -> str:
    """
    List directory contents.
    
    Args:
        path: Directory path to list
        include_hidden: Include hidden files (starting with .)
    
    Returns:
        Directory listing
    """
    logger.debug(f"Listing directory: {path}")
    
    try:
        dir_path = Path(path)
        if not dir_path.exists():
            return f"[ERROR] Directory not found: {path}"
        if not dir_path.is_dir():
            return f"[ERROR] Not a directory: {path}"
        
        items = []
        for item in sorted(dir_path.iterdir()):
            if not include_hidden and item.name.startswith("."):
                continue
            suffix = "/" if item.is_dir() else ""
            items.append(f"{item.name}{suffix}")
        
        return "\n".join(items) if items else "(empty)"
        
    except Exception as e:
        logger.exception(f"Directory list failed: {path}")
        return f"[ERROR] {str(e)}"
