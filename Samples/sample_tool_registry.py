# sample_tool_registry.py
import inspect
from typing import Callable, Dict, Any

# 全局工具注册表
TJ_TOOLS_REGISTRY: Dict[str, dict] = {}

def tj_tool(name: str, description: str):
    """
    将普通的异步 Python 函数注册为大模型可用的 Tool。
    自动提取类型注解并生成 JSON Schema。
    """
    def decorator(func: Callable):
        sig = inspect.signature(func)
        # 这里仅作骨架展示，实际实现需要将 sig.parameters 转换为 JSON Schema 的 properties
        parameters_schema = {
            "type": "object",
            "properties": {}, # 交给 AI 助手去实现具体的映射逻辑
            "required": []
        }
        
        tool_definition = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters_schema
            }
        }
        
        TJ_TOOLS_REGISTRY[name] = {
            "definition": tool_definition,
            "executable": func
        }
        return func
    return decorator

# 使用示例
@tj_tool(name="get_current_time", description="获取系统当前时间")
async def get_current_time(timezone: str = "Asia/Shanghai") -> str:
    import datetime
    # 具体的获取时间逻辑...
    return datetime.datetime.now().isoformat()