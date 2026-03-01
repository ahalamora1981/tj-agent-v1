from __future__ import annotations

import inspect
import json
from typing import Any, Callable, TypeVar, get_type_hints, is_typeddict
from loguru import logger
from ..models import TOOL_REGISTRY

T = TypeVar("T")


def tj_tool(name: str, description: str):
    """
    Decorator to register an async function as a TJ Agent tool.
    Automatically extracts type annotations and generates JSON Schema.
    
    Usage:
        @tj_tool(name="bash", description="Execute a bash command")
        async def bash(command: str, timeout: int = 30) -> str:
            ...
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        sig = inspect.signature(func)
        parameters_schema = _signature_to_json_schema(func, sig)
        
        TOOL_REGISTRY.register(
            name=name,
            description=description,
            parameters_schema=parameters_schema,
            executable=func
        )
        
        logger.debug(f"Registered tool: {name}")
        return func
    return decorator


def _signature_to_json_schema(func: Callable[..., Any], sig: inspect.Signature) -> dict[str, Any]:
    """Convert function signature to JSON Schema for OpenAI function calling."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    
    try:
        type_hints = get_type_hints(func)
    except Exception as e:
        logger.warning(f"Failed to get type hints for {func.__name__}: {e}")
        type_hints = {}
    
    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue
        
        param_type = type_hints.get(param_name, param.annotation if param.annotation != inspect.Parameter.empty else Any)
        
        json_type = _python_type_to_json_type(param_type)
        
        property_schema: dict[str, Any] = {
            "type": json_type,
            "description": f"Parameter {param_name}"
        }
        
        if param.default != inspect.Parameter.empty:
            property_schema["default"] = param.default
        else:
            required.append(param_name)
        
        if json_type == "object" and is_typeddict(param_type):
            pass
        
        properties[param_name] = property_schema
    
    return {
        "type": "object",
        "properties": properties,
        "required": required
    }


def _python_type_to_json_type(py_type: Any) -> str:
    """Map Python types to JSON Schema types."""
    type_mapping = {
        str: "string",
        int: "integer", 
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }
    
    origin = getattr(py_type, "__origin__", None)
    
    if origin is list:
        return "array"
    if origin is dict:
        return "object"
    if origin is tuple:
        return "array"
    
    if py_type in type_mapping:
        return type_mapping[py_type]
    
    return "string"
