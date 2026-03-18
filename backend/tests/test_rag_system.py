"""Test suite for RAG system content query handling"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import Mock, patch
from rag_system import RAGSystem
from config import Config


class TestRAGSystem(unittest.TestCase):
    """Test cases for RAG system content query handling"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = Config()
        self.patches = []

        self.mock_vector_store = Mock()
        vector_store_patch = patch(
            "rag_system.VectorStore", return_value=self.mock_vector_store
        )
        self.patches.append(vector_store_patch)
        vector_store_patch.start()

        self.mock_document_processor = Mock()
        doc_processor_patch = patch(
            "rag_system.DocumentProcessor", return_value=self.mock_document_processor
        )
        self.patches.append(doc_processor_patch)
        doc_processor_patch.start()

        self.mock_ai_generator = Mock()
        ai_generator_patch = patch(
            "rag_system.AIGenerator", return_value=self.mock_ai_generator
        )
        self.patches.append(ai_generator_patch)
        ai_generator_patch.start()

        self.mock_session_manager = Mock()
        session_manager_patch = patch(
            "rag_system.SessionManager", return_value=self.mock_session_manager
        )
        self.patches.append(session_manager_patch)
        session_manager_patch.start()

        self.rag_system = RAGSystem(self.config)

    def tearDown(self):
        """Clean up patches"""
        for patch_obj in self.patches:
            patch_obj.stop()

    def test_query_calls_ai_generator_with_tools(self):
        """Test that query passes tools to AI generator"""
        self.mock_ai_generator.generate_response.return_value = (
            "Python is a programming language."
        )
        self.rag_system.tool_manager.get_last_sources = Mock(return_value=[])

        response, sources = self.rag_system.query("What is Python?")

        self.mock_ai_generator.generate_response.assert_called_once()

        call_args = self.mock_ai_generator.generate_response.call_args
        self.assertIn("tools", call_args.kwargs)
        tools = call_args.kwargs["tools"]

        tool_names = [tool["name"] for tool in tools]
        self.assertIn("search_course_content", tool_names)
        self.assertIn("get_course_outline", tool_names)

    def test_query_includes_tool_manager(self):
        """Test that query passes tool_manager to AI generator"""
        self.mock_ai_generator.generate_response.return_value = "Answer"
        self.rag_system.tool_manager.get_last_sources = Mock(return_value=[])

        response, sources = self.rag_system.query("Test question")

        call_args = self.mock_ai_generator.generate_response.call_args
        self.assertIn("tool_manager", call_args.kwargs)
        self.assertEqual(call_args.kwargs["tool_manager"], self.rag_system.tool_manager)

    def test_query_retrieves_and_returns_sources(self):
        """Test that query retrieves sources from tool manager"""
        self.mock_ai_generator.generate_response.return_value = "Answer"
        expected_sources = [
            {"display": "Python Course - Lesson 1", "url": "http://example.com/1"},
            {"display": "Python Course - Lesson 2", "url": "http://example.com/2"},
        ]
        self.rag_system.tool_manager.get_last_sources = Mock(
            return_value=expected_sources
        )

        response, sources = self.rag_system.query("Test question")

        self.assertEqual(sources, expected_sources)

    def test_query_with_session_id(self):
        """Test that query handles session management correctly"""
        self.mock_ai_generator.generate_response.return_value = "Answer"
        self.mock_session_manager.get_conversation_history.return_value = (
            "Previous conversation"
        )
        self.rag_system.tool_manager.get_last_sources = Mock(return_value=[])

        session_id = "test_session"
        response, sources = self.rag_system.query("Question", session_id=session_id)

        self.mock_session_manager.get_conversation_history.assert_called_once_with(
            session_id
        )

        call_args = self.mock_ai_generator.generate_response.call_args
        self.assertIn("conversation_history", call_args.kwargs)
        self.assertEqual(
            call_args.kwargs["conversation_history"], "Previous conversation"
        )

        self.mock_session_manager.add_exchange.assert_called_once_with(
            session_id, "Question", "Answer"
        )

    def test_query_without_session_id(self):
        """Test that query works without session ID"""
        self.mock_ai_generator.generate_response.return_value = "Answer"
        self.rag_system.tool_manager.get_last_sources = Mock(return_value=[])

        response, sources = self.rag_system.query("Question")

        self.mock_session_manager.get_conversation_history.assert_not_called()
        self.mock_session_manager.add_exchange.assert_not_called()

    def test_query_format_prompt(self):
        """Test that query formats prompt correctly"""
        self.mock_ai_generator.generate_response.return_value = "Answer"
        self.rag_system.tool_manager.get_last_sources = Mock(return_value=[])

        test_query = "What is machine learning?"
        response, sources = self.rag_system.query(test_query)

        call_args = self.mock_ai_generator.generate_response.call_args
        query_param = call_args.kwargs["query"]
        self.assertIn("Answer this question about course materials:", query_param)
        self.assertIn(test_query, query_param)

    def test_content_query_triggers_search_tool(self):
        """Test end-to-end: content query triggers search tool"""
        self.mock_ai_generator.generate_response.return_value = (
            "Python is a programming language."
        )
        self.rag_system.tool_manager.get_last_sources = Mock(
            return_value=[
                {"display": "Python Course - Lesson 1", "url": "http://example.com/1"}
            ]
        )

        response, sources = self.rag_system.query("What is Python?")

        self.assertEqual(response, "Python is a programming language.")
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["display"], "Python Course - Lesson 1")

    def test_outline_query_triggers_outline_tool(self):
        """Test end-to-end: outline query triggers outline tool"""
        self.mock_ai_generator.generate_response.return_value = (
            "Course: Python Programming\n"
            "Course Link: http://example.com\n"
            "Lessons:\n"
            "  1. Introduction\n"
            "  2. Basics\n"
        )
        self.rag_system.tool_manager.get_last_sources = Mock(return_value=[])

        response, sources = self.rag_system.query("What lessons are in Python course?")

        self.assertIn("Python Programming", response)
        self.assertIn("Introduction", response)
        self.assertIn("Basics", response)

    def test_query_returns_correct_tuple_format(self):
        """Test that query returns (response, sources) tuple"""
        self.mock_ai_generator.generate_response.return_value = "Test answer"
        self.rag_system.tool_manager.get_last_sources = Mock(return_value=[])

        result = self.rag_system.query("Test question")

        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], str)
        self.assertIsInstance(result[1], list)

    def test_query_with_empty_sources(self):
        """Test that query handles empty sources correctly"""
        self.mock_ai_generator.generate_response.return_value = "Answer"
        self.rag_system.tool_manager.get_last_sources = Mock(return_value=[])

        response, sources = self.rag_system.query("Question")

        self.assertEqual(sources, [])

    def test_multiple_queries_with_session(self):
        """Test that multiple queries maintain conversation context"""
        self.mock_ai_generator.generate_response.side_effect = [
            "First answer",
            "Second answer",
        ]
        self.mock_session_manager.get_conversation_history.return_value = (
            "User: First?\nAssistant: First answer"
        )
        self.rag_system.tool_manager.get_last_sources = Mock(return_value=[])

        session_id = "test_session"

        response1, sources1 = self.rag_system.query(
            "First question?", session_id=session_id
        )
        response2, sources2 = self.rag_system.query("Follow-up?", session_id=session_id)

        self.assertEqual(self.mock_ai_generator.generate_response.call_count, 2)
        self.assertEqual(self.mock_session_manager.add_exchange.call_count, 2)

    def test_tools_registered_during_initialization(self):
        """Test that both tools are registered during RAG system initialization"""
        tool_defs = self.rag_system.tool_manager.get_tool_definitions()

        tool_names = [tool["name"] for tool in tool_defs]
        self.assertIn("search_course_content", tool_names)
        self.assertIn("get_course_outline", tool_names)
        self.assertEqual(len(tool_defs), 2)


if __name__ == "__main__":
    unittest.main()
