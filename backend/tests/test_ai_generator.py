"""Test suite for AIGenerator tool calling functionality"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import Mock, patch
import json
from ai_generator import AIGenerator


class MockToolCall:
    """Mock tool call object"""

    def __init__(self, id, name, arguments):
        self.id = id
        self.function = Mock()
        self.function.name = name
        self.function.arguments = arguments


class MockMessage:
    """Mock message object"""

    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class MockChoice:
    """Mock choice object"""

    def __init__(self, message):
        self.message = message


class MockResponse:
    """Mock response object"""

    def __init__(self, content=None, tool_calls=None):
        mock_message = MockMessage(content, tool_calls)
        mock_choice = MockChoice(mock_message)
        self.choices = [mock_choice]


class TestAIGenerator(unittest.TestCase):
    """Test cases for AIGenerator tool calling"""

    def setUp(self):
        """Set up test fixtures"""
        self.api_key = "test_api_key"
        self.model = "glm-4-plus"

    @patch("ai_generator.zhipuai.ZhipuAI")
    def test_convert_tools_to_zhipu_format(self, mock_zhipuai):
        """Test that tools are correctly converted from Claude to Zhipu AI format"""
        generator = AIGenerator(self.api_key, self.model)

        # Input tools in Claude format
        claude_tools = [
            {
                "name": "search_course_content",
                "description": "Search course materials",
                "input_schema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
            {
                "name": "get_course_outline",
                "description": "Get course outline",
                "input_schema": {
                    "type": "object",
                    "properties": {"course_name": {"type": "string"}},
                    "required": ["course_name"],
                },
            },
        ]

        # Convert
        zhipu_tools = generator._convert_tools_to_zhipu_format(claude_tools)

        # Verify conversion
        self.assertEqual(len(zhipu_tools), 2)

        # Check first tool
        self.assertEqual(zhipu_tools[0]["type"], "function")
        self.assertEqual(zhipu_tools[0]["function"]["name"], "search_course_content")
        self.assertEqual(
            zhipu_tools[0]["function"]["description"], "Search course materials"
        )
        self.assertEqual(zhipu_tools[0]["function"]["parameters"]["type"], "object")

        # Check second tool
        self.assertEqual(zhipu_tools[1]["type"], "function")
        self.assertEqual(zhipu_tools[1]["function"]["name"], "get_course_outline")

    @patch("ai_generator.zhipuai.ZhipuAI")
    def test_tools_included_in_api_call(self, mock_zhipuai):
        """Test that tools are included in API call when provided"""
        # Setup mock client
        mock_client = Mock()
        mock_response = MockResponse(content="Direct answer")
        mock_client.chat.completions.create.return_value = mock_response
        mock_zhipuai.return_value = mock_client

        generator = AIGenerator(self.api_key, self.model)

        # Define tools
        tools = [
            {
                "name": "search_course_content",
                "description": "Search",
                "input_schema": {"type": "object"},
            }
        ]

        # Generate response with tools
        result = generator.generate_response(query="What is Python?", tools=tools)

        # Verify API call included tools
        call_args = mock_client.chat.completions.create.call_args
        self.assertIn("tools", call_args.kwargs)
        self.assertIn("tool_choice", call_args.kwargs)
        self.assertEqual(call_args.kwargs["tool_choice"], "auto")

    @patch("ai_generator.zhipuai.ZhipuAI")
    def test_tools_not_included_when_not_provided(self, mock_zhipuai):
        """Test that tools are not included when not provided"""
        # Setup mock client
        mock_client = Mock()
        mock_response = MockResponse(content="Direct answer")
        mock_client.chat.completions.create.return_value = mock_response
        mock_zhipuai.return_value = mock_client

        generator = AIGenerator(self.api_key, self.model)

        # Generate response without tools
        result = generator.generate_response(query="Hello")

        # Verify API call did not include tools
        call_args = mock_client.chat.completions.create.call_args
        self.assertNotIn("tools", call_args.kwargs)
        self.assertNotIn("tool_choice", call_args.kwargs)

    @patch("ai_generator.zhipuai.ZhipuAI")
    def test_base_params_configuration(self, mock_zhipuai):
        """Test that base parameters are correctly configured"""
        mock_client = Mock()
        mock_response = MockResponse(content="Answer")
        mock_client.chat.completions.create.return_value = mock_response
        mock_zhipuai.return_value = mock_client

        generator = AIGenerator(self.api_key, self.model)

        # Generate response
        result = generator.generate_response(query="Test")

        # Verify base params in API call
        call_args = mock_client.chat.completions.create.call_args
        self.assertEqual(call_args.kwargs["model"], self.model)
        self.assertEqual(call_args.kwargs["temperature"], 0)
        self.assertEqual(call_args.kwargs["max_tokens"], 800)

    @patch("ai_generator.zhipuai.ZhipuAI")
    def test_sequential_tool_calling_two_rounds(self, mock_zhipuai):
        """Test that two sequential tool calls work correctly with context preserved"""
        mock_client = Mock()
        mock_zhipuai.return_value = mock_client

        # Mock tool manager
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = [
            "Python Course - Lesson 1: Introduction to Python",
            "Python is a high-level programming language...",
        ]

        # First response: requests get_course_outline tool
        first_response = MockResponse(
            content=None,
            tool_calls=[MockToolCall("call_1", "get_course_outline", '{"course_name": "Python"}')],
        )

        # Second response: requests search_course_content tool
        second_response = MockResponse(
            content=None,
            tool_calls=[MockToolCall("call_2", "search_course_content", '{"query": "Python"}')],
        )

        # Third response: final answer
        final_response = MockResponse(content="Python is a high-level programming language...")

        mock_client.chat.completions.create.side_effect = [
            first_response,
            second_response,
            final_response,
        ]

        generator = AIGenerator(self.api_key, self.model)

        tools = [
            {
                "name": "get_course_outline",
                "description": "Get course outline",
                "input_schema": {"type": "object"},
            },
            {
                "name": "search_course_content",
                "description": "Search course content",
                "input_schema": {"type": "object"},
            },
        ]

        result = generator.generate_response(
            query="What is covered in lesson 1 of the Python course?", tools=tools, tool_manager=mock_tool_manager
        )

        # Verify result
        self.assertEqual(result, "Python is a high-level programming language...")

        # Verify 3 API calls were made (2 tool calls + 1 final response)
        self.assertEqual(mock_client.chat.completions.create.call_count, 3)

        # Verify tool manager was called twice
        self.assertEqual(mock_tool_manager.execute_tool.call_count, 2)
        mock_tool_manager.execute_tool.assert_any_call("get_course_outline", course_name="Python")
        mock_tool_manager.execute_tool.assert_any_call("search_course_content", query="Python")

        # Verify messages array grew correctly between rounds
        third_call_args = mock_client.chat.completions.create.call_args_list[2]
        self.assertEqual(len(third_call_args.kwargs["messages"]), 6)  # system, user, assistant, tool, assistant, tool

    @patch("ai_generator.zhipuai.ZhipuAI")
    def test_sequential_tool_calling_stops_after_one_round(self, mock_zhipuai):
        """Test that loop terminates when Claude doesn't request a second tool"""
        mock_client = Mock()
        mock_zhipuai.return_value = mock_client

        # Mock tool manager
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Python Course Outline"

        # First response: requests tool
        first_response = MockResponse(
            content=None,
            tool_calls=[MockToolCall("call_1", "get_course_outline", '{"course_name": "Python"}')],
        )

        # Second response: direct answer, no more tools
        second_response = MockResponse(content="The Python course covers 10 lessons.")

        mock_client.chat.completions.create.side_effect = [first_response, second_response]

        generator = AIGenerator(self.api_key, self.model)

        tools = [
            {
                "name": "get_course_outline",
                "description": "Get course outline",
                "input_schema": {"type": "object"},
            }
        ]

        result = generator.generate_response(
            query="What's in the Python course?", tools=tools, tool_manager=mock_tool_manager
        )

        # Verify result
        self.assertEqual(result, "The Python course covers 10 lessons.")

        # Verify 2 API calls were made (1 tool call + 1 final response)
        self.assertEqual(mock_client.chat.completions.create.call_count, 2)

        # Verify tool manager was called once
        self.assertEqual(mock_tool_manager.execute_tool.call_count, 1)

    @patch("ai_generator.zhipuai.ZhipuAI")
    def test_max_rounds_limit(self, mock_zhipuai):
        """Test that exactly MAX_TOOL_ROUNDS rounds are executed even if more tool calls are requested"""
        mock_client = Mock()
        mock_zhipuai.return_value = mock_client

        # Mock tool manager
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = ["Result 1", "Result 2"]

        # First round response: requests tool
        first_response = MockResponse(
            content=None,
            tool_calls=[MockToolCall("call_1", "tool1", '{}')],
        )

        # Second round response: requests another tool
        second_response = MockResponse(
            content=None,
            tool_calls=[MockToolCall("call_2", "tool2", '{}')],
        )

        # Third response would be requested but should not happen due to limit
        final_response = MockResponse(content="Final answer after max rounds")

        mock_client.chat.completions.create.side_effect = [
            first_response,
            second_response,
            final_response,
        ]

        generator = AIGenerator(self.api_key, self.model)

        tools = [
            {"name": "tool1", "description": "Tool 1", "input_schema": {"type": "object"}},
            {"name": "tool2", "description": "Tool 2", "input_schema": {"type": "object"}},
        ]

        result = generator.generate_response(
            query="Test", tools=tools, tool_manager=mock_tool_manager
        )

        # Verify result
        self.assertEqual(result, "Final answer after max rounds")

        # Verify 3 API calls: 2 tool rounds + 1 final call (not a 4th call even though AI requested more)
        self.assertEqual(mock_client.chat.completions.create.call_count, 3)

        # Verify tool manager was called exactly twice
        self.assertEqual(mock_tool_manager.execute_tool.call_count, 2)

    @patch("ai_generator.zhipuai.ZhipuAI")
    def test_tool_execution_error_handling(self, mock_zhipuai):
        """Test that errors in tool execution are handled gracefully"""
        mock_client = Mock()
        mock_zhipuai.return_value = mock_client

        # Mock tool manager that raises an error
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = [
            "Success result",
            Exception("Tool failed"),
        ]

        # First response: requests tool that succeeds
        first_response = MockResponse(
            content=None,
            tool_calls=[MockToolCall("call_1", "tool1", '{}')],
        )

        # Second response: requests tool that fails
        second_response = MockResponse(
            content=None,
            tool_calls=[MockToolCall("call_2", "tool2", '{}')],
        )

        # Third response: AI handles the error
        final_response = MockResponse(content="I encountered an error but can still help.")

        mock_client.chat.completions.create.side_effect = [first_response, second_response, final_response]

        generator = AIGenerator(self.api_key, self.model)

        tools = [
            {"name": "tool1", "description": "Tool 1", "input_schema": {"type": "object"}},
            {"name": "tool2", "description": "Tool 2", "input_schema": {"type": "object"}},
        ]

        result = generator.generate_response(
            query="Test", tools=tools, tool_manager=mock_tool_manager
        )

        # Verify result
        self.assertEqual(result, "I encountered an error but can still help.")

        # Verify error message was passed to AI in tool result
        second_call_args = mock_client.chat.completions.create.call_args_list[2]
        messages = second_call_args.kwargs["messages"]
        tool_message = messages[-1]
        self.assertEqual(tool_message["role"], "tool")
        self.assertIn("Tool execution error", tool_message["content"])

    @patch("ai_generator.zhipuai.ZhipuAI")
    def test_direct_response_without_tools(self, mock_zhipuai):
        """Test that queries without tool needs still work (backward compatibility)"""
        mock_client = Mock()
        mock_zhipuai.return_value = mock_client

        # Response: direct answer, no tools
        response = MockResponse(content="2 + 2 = 4")

        mock_client.chat.completions.create.return_value = response

        generator = AIGenerator(self.api_key, self.model)

        result = generator.generate_response(query="What is 2+2?")

        # Verify result
        self.assertEqual(result, "2 + 2 = 4")

        # Verify only 1 API call was made (no tool calls)
        self.assertEqual(mock_client.chat.completions.create.call_count, 1)

    @patch("ai_generator.zhipuai.ZhipuAI")
    def test_conversation_context_preserved(self, mock_zhipuai):
        """Test that messages array grows correctly between rounds"""
        mock_client = Mock()
        mock_zhipuai.return_value = mock_client

        # Mock tool manager
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Tool result"

        # First response: requests tool
        first_response = MockResponse(
            content=None,
            tool_calls=[MockToolCall("call_1", "tool1", '{}')],
        )

        # Second response: final answer
        final_response = MockResponse(content="Final answer")

        mock_client.chat.completions.create.side_effect = [first_response, final_response]

        generator = AIGenerator(self.api_key, self.model)

        tools = [
            {"name": "tool1", "description": "Tool 1", "input_schema": {"type": "object"}},
        ]

        result = generator.generate_response(
            query="Test", tools=tools, tool_manager=mock_tool_manager
        )

        # Verify messages array after first round
        first_call_args = mock_client.chat.completions.create.call_args_list[0]
        self.assertEqual(len(first_call_args.kwargs["messages"]), 2)  # system, user

        # Verify messages array after second round
        second_call_args = mock_client.chat.completions.create.call_args_list[1]
        self.assertEqual(len(second_call_args.kwargs["messages"]), 4)  # system, user, assistant, tool

        # Verify final call doesn't have tools
        final_call_args = mock_client.chat.completions.create.call_args_list[1]
        self.assertNotIn("tools", final_call_args.kwargs)

    @patch("ai_generator.zhipuai.ZhipuAI")
    def test_no_tool_manager_provided(self, mock_zhipuai):
        """Test that behavior when tool_manager is None but response has tool calls"""
        mock_client = Mock()
        mock_zhipuai.return_value = mock_client

        # Response: requests tool but no tool manager provided
        response = MockResponse(
            content="Tool not available",
            tool_calls=[MockToolCall("call_1", "tool1", '{}')],
        )

        mock_client.chat.completions.create.return_value = response

        generator = AIGenerator(self.api_key, self.model)

        tools = [
            {"name": "tool1", "description": "Tool 1", "input_schema": {"type": "object"}},
        ]

        # Generate response without tool_manager
        result = generator.generate_response(query="Test", tools=tools, tool_manager=None)

        # Verify tool was not executed (because tool_manager is None)
        # The response should return the assistant's content directly
        self.assertEqual(result, "Tool not available")

        # Verify only 1 API call was made (no tool execution)
        self.assertEqual(mock_client.chat.completions.create.call_count, 1)


if __name__ == "__main__":
    unittest.main()
