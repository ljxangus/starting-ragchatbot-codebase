import zhipuai
from typing import List, Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass, field


class ToolExecutionState(Enum):
    """States for the tool execution state machine."""
    INITIAL = "initial"
    CALLING_API = "calling_api"
    CHECKING_RESPONSE = "checking_response"
    EXECUTING_TOOLS = "executing_tools"
    CHECKING_COMPLETION = "checking_completion"
    ERROR_HANDLING = "error_handling"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExecutionContext:
    """Immutable context for tool execution."""
    messages: tuple = field(default_factory=tuple)
    round_count: int = 0
    last_response: Optional[Any] = None
    last_error: Optional[str] = None
    result: Optional[str] = None
    errors: tuple = field(default_factory=tuple)
    api_params: Dict = field(default_factory=dict)

    def with_messages(self, messages: List[Dict]) -> "ExecutionContext":
        return dataclasses.replace(
            self,
            messages=tuple(messages)
        )

    def with_new_messages(self, new_messages: List[Dict]) -> "ExecutionContext":
        return dataclasses.replace(
            self,
            messages=tuple(self.messages) + tuple(new_messages)
        )

    def increment_round(self) -> "ExecutionContext":
        return dataclasses.replace(
            self,
            round_count=self.round_count + 1
        )

    def with_last_response(self, response: Any) -> "ExecutionContext":
        return dataclasses.replace(
            self,
            last_response=response
        )

    def with_error(self, error: str) -> "ExecutionContext":
        return dataclasses.replace(
            self,
            last_error=error,
            errors=tuple(self.errors) + (error,)
        )

    def clear_error(self) -> "ExecutionContext":
        return dataclasses.replace(
            self,
            last_error=None
        )

    def with_result(self, result: str) -> "ExecutionContext":
        return dataclasses.replace(
            self,
            result=result
        )


import dataclasses


class ToolExecutionStateMachine:
    """
    State machine for managing sequential tool calling.

    States:
    - INITIAL: Starting state
    - CALLING_API: Making API request
    - CHECKING_RESPONSE: Determining if tools are needed
    - EXECUTING_TOOLS: Running tool calls
    - CHECKING_COMPLETION: Determining if done
    - ERROR_HANDLING: Processing errors
    - FINALIZING: Making final non-tool call
    - COMPLETED: Success terminal state
    - FAILED: Failure terminal state
    """

    def __init__(
        self,
        max_rounds: int,
        client,
        base_params: Dict,
        tool_manager,
        recovery_strategy: str = "continue_with_errors"
    ):
        self.max_rounds = max_rounds
        self.client = client
        self.base_params = base_params
        self.tool_manager = tool_manager
        self.recovery_strategy = recovery_strategy
        self.current_state = ToolExecutionState.INITIAL
        self.context = ExecutionContext()
        self.transition_history = []
        self.initial_api_params = {}

    def execute(self, initial_messages: List[Dict], api_params: Optional[Dict] = None) -> str:
        """Execute the state machine and return final result."""
        self.context = ExecutionContext(
            messages=tuple(initial_messages),
            api_params=api_params or {}
        )
        self.initial_api_params = api_params or {}

        while self.current_state not in [ToolExecutionState.COMPLETED, ToolExecutionState.FAILED]:
            self._transition_state()

        if self.current_state == ToolExecutionState.FAILED:
            return self.context.result or "Execution failed"

        return self.context.result or ""

    def _transition_state(self):
        """Perform state transition based on current state and context."""
        old_state = self.current_state
        new_state = self._get_next_state()

        self.transition_history.append(
            (old_state, new_state)
        )

        self.current_state = new_state
        self._execute_state_action()

    def _get_next_state(self) -> ToolExecutionState:
        """Determine next state based on current state and context."""
        state_rules = {
            ToolExecutionState.INITIAL: ToolExecutionState.CALLING_API,
            ToolExecutionState.CALLING_API: ToolExecutionState.CHECKING_RESPONSE,
            ToolExecutionState.CHECKING_RESPONSE: self._check_response_result(),
            ToolExecutionState.EXECUTING_TOOLS: ToolExecutionState.CHECKING_COMPLETION,
            ToolExecutionState.CHECKING_COMPLETION: self._check_completion_result(),
            ToolExecutionState.ERROR_HANDLING: self._get_recovery_state(),
            ToolExecutionState.FINALIZING: ToolExecutionState.COMPLETED,
        }
        return state_rules.get(self.current_state, ToolExecutionState.FAILED)

    def _execute_state_action(self):
        """Execute the action for the current state."""
        actions = {
            ToolExecutionState.CALLING_API: self._action_call_api,
            ToolExecutionState.EXECUTING_TOOLS: self._action_execute_tools,
            ToolExecutionState.FINALIZING: self._action_finalize,
            ToolExecutionState.ERROR_HANDLING: self._action_handle_error,
        }

        action = actions.get(self.current_state)
        if action:
            action()

    def _check_response_result(self) -> ToolExecutionState:
        """Determine next state after checking API response."""
        if self.context.last_error:
            return ToolExecutionState.ERROR_HANDLING

        if not self.context.last_response:
            return ToolExecutionState.FAILED

        if not self._has_tool_calls(self.context.last_response):
            # Direct answer, no tools needed
            return ToolExecutionState.COMPLETED

        return ToolExecutionState.EXECUTING_TOOLS

    def _check_completion_result(self) -> ToolExecutionState:
        """Determine next state after executing tools."""
        if self.context.round_count >= self.max_rounds:
            return ToolExecutionState.FINALIZING
        return ToolExecutionState.CALLING_API

    def _get_recovery_state(self) -> ToolExecutionState:
        """Determine recovery state based on strategy."""
        strategies = {
            "fail_fast": ToolExecutionState.FAILED,
            "continue_with_errors": ToolExecutionState.CALLING_API,
            "finalize_now": ToolExecutionState.FINALIZING,
        }
        return strategies.get(self.recovery_strategy, ToolExecutionState.FAILED)

    def _action_call_api(self):
        """Make API call."""
        try:
            params = self._build_api_params()
            response = self.client.chat.completions.create(**params)
            self.context = self.context.with_last_response(response)

            # If direct answer, store it
            if not self._has_tool_calls(response):
                self.context = self.context.with_result(
                    response.choices[0].message.content or ""
                )

        except Exception as e:
            self.context = self.context.with_error(str(e))

    def _action_execute_tools(self):
        """Execute tool calls from last response."""
        response = self.context.last_response
        tool_calls = response.choices[0].message.tool_calls

        new_messages = []

        # Build assistant message
        assistant_message = self._build_assistant_message(response)
        new_messages.append(assistant_message)

        # Execute each tool
        for tool_call in tool_calls:
            try:
                result = self.tool_manager.execute_tool(
                    tool_call.function.name,
                    **json.loads(tool_call.function.arguments)
                )
                new_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
            except Exception as e:
                error_msg = f"Tool execution error: {str(e)}"
                new_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": error_msg
                })

        # Update context
        self.context = (
            self.context
            .with_new_messages(new_messages)
            .increment_round()
        )

    def _action_finalize(self):
        """Make final non-tool call."""
        try:
            params = {
                **self.base_params,
                "messages": list(self.context.messages)
            }
            response = self.client.chat.completions.create(**params)
            self.context = self.context.with_result(
                response.choices[0].message.content or ""
            )
        except Exception as e:
            self.context = self.context.with_error(f"Final call failed: {e}")

    def _action_handle_error(self):
        """Handle error based on strategy."""
        if self.recovery_strategy == "fail_fast":
            if self.context.last_response:
                self.context = self.context.with_result(
                    self.context.last_response.choices[0].message.content or ""
                )
        elif self.recovery_strategy == "continue_with_errors":
            self.context = self.context.clear_error()

    def _build_api_params(self) -> Dict:
        """Build API parameters for next call."""
        params = {**self.base_params, "messages": list(self.context.messages)}

        if self.context.round_count == 0 and self.initial_api_params:
            # First round - include tools from initial params
            for key, value in self.initial_api_params.items():
                if key not in ["messages", "model", "temperature", "max_tokens"]:
                    params[key] = value

        return params

    def _build_assistant_message(self, response: Any) -> Dict:
        """Build assistant message from API response."""
        assistant_message = {
            "role": "assistant",
            "content": response.choices[0].message.content or "",
            "tool_calls": [],
        }

        for tool_call in response.choices[0].message.tool_calls:
            assistant_message["tool_calls"].append(
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
            )

        return assistant_message

    def _has_tool_calls(self, response: Any) -> bool:
        """Check if response contains tool calls."""
        if not self.tool_manager:
            return False
        if not hasattr(response.choices[0].message, 'tool_calls'):
            return False
        tool_calls = response.choices[0].message.tool_calls
        return tool_calls is not None and len(tool_calls) > 0


import json


class AIGenerator:
    """Handles interactions with Zhipu AI's GLM-4 API for generating responses"""

    # Maximum sequential tool calling rounds per query
    MAX_TOOL_ROUNDS = 2

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to tools for course information.

Tool Usage:
- **get_course_outline**: Use for questions about course structure, syllabus, lesson lists, or what topics are covered in a course
  - Returns: course title, course link, and complete lesson list with numbers and titles
- **search_course_content**: Use for questions about specific course content, topics within lessons, or detailed educational materials
  - Returns: relevant content chunks from course materials
- **Multi-step reasoning allowed**: You may call tools sequentially (up to 2 rounds total per query) to gather necessary information
- In each round, analyze the previous tool results and decide whether to call another tool
- Use tool results from previous rounds to inform next tool calls when needed (e.g., get course outline first, then search specific lesson)
- After gathering all necessary information (or reaching the 2-round limit), provide your final answer
- Synthesize tool results into accurate, fact-based responses
- If tool yields no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Course outline/structure questions**: Use get_course_outline tool
- **Course content questions**: Use search_course_content tool
- **No meta-commentary**:
  - Provide direct answers only — no reasoning process, tool explanations, or question-type analysis
  - Do not mention "based on the tool results"

All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, model: str):
        self.client = zhipuai.ZhipuAI(api_key=api_key)
        self.model = model

        # Pre-build base API parameters
        self.base_params = {"model": self.model, "temperature": 0, "max_tokens": 800}

    def generate_response(
        self,
        query: str,
        conversation_history: Optional[str] = None,
        tools: Optional[List] = None,
        tool_manager=None,
    ) -> str:
        """
        Generate AI response with optional tool usage and conversation context.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        # Prepare messages for Zhipu AI
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": query},
        ]

        # Prepare API call parameters efficiently
        api_params = {
            **self.base_params,
            "messages": messages,
        }

        # Add tools if available
        if tools:
            # Convert Claude tool format to Zhipu AI format
            zhipu_tools = self._convert_tools_to_zhipu_format(tools)
            api_params["tools"] = zhipu_tools
            api_params["tool_choice"] = "auto"

        # Execute sequential tool rounds or direct response using state machine
        return self._execute_tool_rounds(messages, api_params, tool_manager)

    def _convert_tools_to_zhipu_format(self, claude_tools: List) -> List[Dict]:
        """Convert Claude tool format to Zhipu AI format"""
        zhipu_tools = []
        for tool in claude_tools:
            zhipu_tool = {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                },
            }
            zhipu_tools.append(zhipu_tool)
        return zhipu_tools

    def _execute_tool_rounds(
        self, base_messages: List, api_params: Dict, tool_manager
    ) -> str:
        """
        Execute up to MAX_TOOL_ROUNDS of sequential tool calling using state machine.

        Args:
            base_messages: Initial messages list (system + user query)
            api_params: API parameters including tools if available
            tool_manager: Manager to execute tools

        Returns:
            Final response text after tool execution or direct response
        """
        # If no tool_manager, make direct API call using provided api_params
        if not tool_manager:
            response = self.client.chat.completions.create(**api_params)
            return response.choices[0].message.content or ""

        # If no tools in api_params, make direct API call
        if "tools" not in api_params:
            params = {**self.base_params, "messages": base_messages}
            response = self.client.chat.completions.create(**params)
            return response.choices[0].message.content or ""

        # Use state machine for tool execution
        state_machine = ToolExecutionStateMachine(
            max_rounds=self.MAX_TOOL_ROUNDS,
            client=self.client,
            base_params=self.base_params,
            tool_manager=tool_manager,
            recovery_strategy="continue_with_errors"
        )

        return state_machine.execute(base_messages, api_params)

    def _append_tool_results(
        self, assistant_choice, base_messages: List, tool_manager
    ) -> List:
        """
        Legacy method - execute tool calls and append results to messages for next round.

        Args:
            assistant_choice: The assistant's response containing tool use requests
            base_messages: Current messages list
            tool_manager: Manager to execute tools

        Returns:
            Updated messages list with tool calls and results appended
        """
        messages = base_messages.copy()

        assistant_message = {
            "role": "assistant",
            "content": assistant_choice.message.content or "",
            "tool_calls": [],
        }

        for tool_call in assistant_choice.message.tool_calls:
            assistant_message["tool_calls"].append(
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
            )

        messages.append(assistant_message)

        for tool_call in assistant_choice.message.tool_calls:
            try:
                tool_result = tool_manager.execute_tool(
                    tool_call.function.name, **json.loads(tool_call.function.arguments)
                )
                messages.append(
                    {"role": "tool", "tool_call_id": tool_call.id, "content": tool_result}
                )
            except Exception as e:
                messages.append(
                    {"role": "tool", "tool_call_id": tool_call.id, "content": f"Tool execution error: {str(e)}"}
                )

        return messages

    def _handle_tool_execution(
        self, _initial_response, base_messages: List, tool_manager
    ):
        """
        Legacy method - use _execute_tool_rounds instead.
        Handle execution of tool calls and get follow-up response.
        """
        # Build api_params from base_params and messages
        api_params = {**self.base_params, "messages": base_messages}

        # Call new implementation
        return self._execute_tool_rounds(base_messages, api_params, tool_manager)
