from __future__ import annotations

from typing import Any, Optional, AsyncIterator, Callable
from loguru import logger

from ..models import AgentState, AgentConfig, Message, ToolCall, ToolResult, TOOL_REGISTRY
from ..tools.executor import ToolExecutor
from .llm_client import LLMClient, LLMClientManager


def default_stream_callback(chunk: str) -> None:
    """Default callback that prints chunk to stdout."""
    print(chunk, end="", flush=True)


class ReActLoop:
    """
    ReAct (Reason + Act) Loop Controller.
    
    Implements the core agent loop:
    1. Send messages + tools to LLM
    2. LLM decides: respond OR call a tool
    3. If tool call: execute and add observation
    4. Repeat until completion or max iterations
    """
    
    def __init__(
        self,
        state: AgentState,
        llm_client: LLMClient,
        tool_executor: ToolExecutor,
        stream_callback: Any = None
    ) -> None:
        self.state = state
        self.llm = llm_client
        self.executor = tool_executor
        self.stream_callback = stream_callback
    
    async def run(self, user_input: str) -> str:
        """
        Run the ReAct loop until completion.
        Uses streaming internally for better UX.
        
        Args:
            user_input: Initial user message
        
        Returns:
            Final assistant response
        """
        user_message = Message(role="user", content=user_input)
        self.state.add_message(user_message)
        
        system_prompt = self.state.config.system_prompt
        if system_prompt:
            system_message = Message(role="system", content=system_prompt)
            messages_with_system = [system_message.to_openai_format()] + self.state.get_context_messages()
        else:
            messages_with_system = self.state.get_context_messages()
        
        logger.info(f"Starting ReAct loop for session: {self.state.config.session_id}")
        
        full_response = ""
        
        while not self.state.is_complete and self.state.iteration_count < self.state.config.max_iterations:
            self.state.iteration_count += 1
            logger.debug(f"Iteration {self.state.iteration_count}")
            
            # Get fresh messages including tool results
            messages_with_system = [system_message.to_openai_format()] + self.state.get_context_messages()
            
            response = await self._step_streaming(messages_with_system)
            
            if self.state.is_complete:
                break
            
            if response is None:
                logger.warning("LLM returned no response, ending loop")
                self.state.last_error = "No response from LLM"
                break
            
            full_response = response
        
        if self.state.iteration_count >= self.state.config.max_iterations:
            self.state.last_error = f"Max iterations ({self.state.config.max_iterations}) reached"
        
        if not full_response:
            final_message = next(
                (m for m in reversed(self.state.messages) if m.role == "assistant" and m.content),
                None
            )
            full_response = (final_message.content or "[No response]") if final_message else "[No response]"
        
        return full_response
    
    async def _step_streaming(self, messages: list[dict[str, Any]]) -> Optional[str]:
        """
        Execute one step with streaming response.
        
        Args:
            messages: List of message dicts to send to LLM
        
        Returns:
            Full assistant response content or None
        """
        tool_definitions = self._get_tool_definitions()
        
        logger.info(f"Calling LLM with {len(messages)} messages, {len(tool_definitions)} tools")
        
        try:
            # Use non-streaming to get tool_calls properly
            logger.info(f"Sending messages: {len(messages)}")
            for i, msg in enumerate(messages):
                content = msg.get('content', '')[:500] if msg.get('content') else ''
                logger.info(f"Msg {i}: role={msg['role']}, content={content}")
            
            response = await self.llm.chat(
                messages=messages,
                model=self.state.config.model,
                temperature=self.state.config.temperature,
                tools=tool_definitions if tool_definitions else None,
                stream=False
            )
            
            # Parse response like _step does
            response_dict: dict[str, Any] = response  # type: ignore
            assistant_message = self._parse_response(response_dict)
            
            logger.info(f"Assistant message: content={assistant_message.content is not None}, tool_calls={assistant_message.tool_calls is not None}")
            
            if assistant_message.tool_calls:
                logger.info(f"Executing {len(assistant_message.tool_calls)} tool calls")
                # Add assistant message with tool_calls to state first
                self.state.add_message(assistant_message)
                for tool_call in assistant_message.tool_calls:
                    logger.info(f"Tool call: {tool_call.name} - {tool_call.arguments}")
                    await self._execute_tool(tool_call)
                # Continue loop after tool execution
                self.state.is_complete = False
                return ""
            elif assistant_message.content:
                logger.info("Setting complete - has content")
                # Stream the content to callback if available
                if assistant_message.content and self.stream_callback:
                    self.stream_callback(assistant_message.content)
                self.state.add_message(assistant_message)
                self.state.is_complete = True
                return assistant_message.content
            else:
                logger.warning("No content and no tool calls - ending loop")
                self.state.is_complete = True
                return ""
                
        except Exception as e:
            logger.exception("LLM API call failed")
            self.state.last_error = str(e)
            self.state.is_complete = True
            return None
    
    async def _step(self) -> Optional[dict[str, Any]]:
        """
        Execute one step of the ReAct loop.
        
        Returns:
            LLM response dict or None
        """
        messages = self.state.get_context_messages()
        
        logger.info(f"Total messages in context: {len(messages)}")
        for i, msg in enumerate(messages):
            role = msg.get('role', '')
            content = str(msg.get('content', ''))[:300] if msg.get('content') else ''
            tool_call_id = msg.get('tool_call_id', '')
            tool_calls = str(msg.get('tool_calls', ''))[:100] if msg.get('tool_calls') else ''
            logger.info(f"Context Msg {i}: role={role}, tool_call_id={tool_call_id}, tool_calls={tool_calls}, content={content}")
        
        tool_definitions = self._get_tool_definitions()
        
        logger.info(f"Calling LLM with {len(messages)} messages, {len(tool_definitions)} tools")
        
        try:
            response = await self.llm.chat(
                messages=messages,
                model=self.state.config.model,
                temperature=self.state.config.temperature,
                tools=tool_definitions if tool_definitions else None,
                stream=False
            )
            logger.info(f"LLM response received")
        except Exception as e:
            logger.exception("LLM API call failed")
            self.state.last_error = str(e)
            self.state.is_complete = True
            return None
        
        response_data = response  # type: ignore[assignment]
        assistant_message = self._parse_response(response_data)  # type: ignore[arg-type]
        
        logger.info(f"Assistant message: content={assistant_message.content is not None}, tool_calls={assistant_message.tool_calls is not None}")
        
        if assistant_message.tool_calls:
            logger.info(f"Executing {len(assistant_message.tool_calls)} tool calls")
            for tool_call in assistant_message.tool_calls:
                await self._execute_tool(tool_call)
        elif assistant_message.content:
            logger.info("Setting complete - has content")
            self.state.add_message(assistant_message)
            self.state.is_complete = True
        else:
            logger.warning("No content and no tool calls - ending loop")
            self.state.is_complete = True
        
        return response_data if isinstance(response_data, dict) else None  # type: ignore[return-value]
    
    async def _execute_tool(self, tool_call: ToolCall) -> None:
        """Execute a tool and add the observation to messages."""
        logger.info(f"Executing tool: {tool_call.name}")
        
        tool_result = await self.executor.execute(tool_call)
        
        result_content = tool_result.content if not tool_result.is_error else f"Error: {tool_result.error_message}"
        logger.info(f"Tool result: {result_content[:200]}...")
        
        result_message = Message(
            role="tool",
            content=result_content,
            tool_call_id=tool_call.id,
            name=tool_call.name
        )
        
        logger.info(f"Tool result message created: {result_message}")
        
        self.state.add_message(result_message)
    
    def _get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get all available tool definitions for LLM."""
        definitions = TOOL_REGISTRY.get_definitions()
        result = []
        for d in definitions:
            if d:
                result.append({
                    "type": d.type,
                    "function": d.function
                })
        return result
    
    def _parse_response(self, response: dict[str, Any]) -> Message:
        """Parse LLM response into a Message object."""
        import json
        
        choices = response.get("choices", [])
        if not choices:
            return Message(role="assistant", content="")
        
        choice = choices[0]
        message_data = choice.get("message", {})
        
        content = message_data.get("content")
        tool_calls_data = message_data.get("tool_calls", [])
        
        tool_calls = None
        if tool_calls_data:
            tool_calls = []
            for i, tc in enumerate(tool_calls_data):
                args = tc.get("function", {}).get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args) if args else {}
                    except json.JSONDecodeError:
                        args = {}
                
                tool_calls.append(ToolCall(
                    id=tc.get("id", f"call_{i}"),
                    name=tc.get("function", {}).get("name", ""),
                    arguments=args
                ))
        
        return Message(
            role="assistant",
            content=content,
            tool_calls=tool_calls
        )


class ReActRunner:
    """
    Runner for the ReAct loop with streaming support.
    """
    
    def __init__(self, config: AgentConfig, stream_callback: Any = None) -> None:
        self.config = config
        self.llm_client: Optional[LLMClient] = None
        self.tool_executor = ToolExecutor()
        self.state: Optional[AgentState] = None
        self.stream_callback = stream_callback
    
    async def run(self, user_input: str) -> str:
        """Run the agent with the given input."""
        async with LLMClientManager.get_instance(
            default_model=self.config.model
        ) as client:
            self.llm_client = client
            self.state = AgentState(config=self.config)
            loop = ReActLoop(self.state, client, self.tool_executor, self.stream_callback)
            return await loop.run(user_input)
    
    async def run_streaming(self, user_input: str) -> AsyncIterator[str]:
        """Run the agent with streaming responses."""
        async with LLMClientManager.get_instance(
            default_model=self.config.model
        ) as client:
            self.llm_client = client
            self.state = AgentState(config=self.config)
            loop = ReActLoop(self.state, client, self.tool_executor)
            
            yield f"Starting agent for: {user_input}\n\n"
            
            result = await loop.run(user_input)
            yield f"\n\nFinal response: {result}"
