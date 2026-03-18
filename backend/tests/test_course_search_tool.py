"""Test suite for CourseSearchTool functionality"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import Mock, MagicMock, patch
from search_tools import CourseSearchTool
from vector_store import SearchResults
from models import CourseChunk


class TestCourseSearchTool(unittest.TestCase):
    """Test cases for CourseSearchTool.execute() method"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_vector_store = Mock()
        self.tool = CourseSearchTool(self.mock_vector_store)

    def test_execute_valid_query_returns_results(self):
        """Test that execute returns formatted results for valid query"""
        # Mock search results
        mock_results = SearchResults(
            documents=["Test content about Python basics"],
            metadata=[
                {
                    "course_title": "Python Programming",
                    "lesson_number": 1,
                    "chunk_index": 0,
                }
            ],
            distances=[0.1],
            error=None,
        )
        self.mock_vector_store.search.return_value = mock_results
        self.mock_vector_store.get_lesson_link.return_value = (
            "http://example.com/lesson1"
        )

        # Execute
        result = self.tool.execute(query="Python basics")

        # Verify search was called correctly
        self.mock_vector_store.search.assert_called_once_with(
            query="Python basics", course_name=None, lesson_number=None
        )

        # Verify result format
        self.assertIn("Python Programming", result)
        self.assertIn("Test content about Python basics", result)
        self.assertIn("Lesson 1", result)

    def test_execute_with_no_results(self):
        """Test that execute handles empty results gracefully"""
        # Mock empty results
        mock_results = SearchResults(
            documents=[], metadata=[], distances=[], error=None
        )
        self.mock_vector_store.search.return_value = mock_results

        # Execute
        result = self.tool.execute(query="nonexistent topic")

        # Verify empty message
        self.assertEqual(result, "No relevant content found.")

    def test_execute_with_course_filter(self):
        """Test that execute passes course_name filter correctly"""
        mock_results = SearchResults(
            documents=["Content"],
            metadata=[{"course_title": "Python Programming", "lesson_number": 1}],
            distances=[0.1],
            error=None,
        )
        self.mock_vector_store.search.return_value = mock_results
        self.mock_vector_store.get_lesson_link.return_value = None

        # Execute with course filter
        result = self.tool.execute(query="basics", course_name="Python")

        # Verify search was called with course filter
        self.mock_vector_store.search.assert_called_once_with(
            query="basics", course_name="Python", lesson_number=None
        )

    def test_execute_with_lesson_filter(self):
        """Test that execute passes lesson_number filter correctly"""
        mock_results = SearchResults(
            documents=["Content"],
            metadata=[{"course_title": "Python Programming", "lesson_number": 2}],
            distances=[0.1],
            error=None,
        )
        self.mock_vector_store.search.return_value = mock_results
        self.mock_vector_store.get_lesson_link.return_value = None

        # Execute with lesson filter
        result = self.tool.execute(query="topic", lesson_number=2)

        # Verify search was called with lesson filter
        self.mock_vector_store.search.assert_called_once_with(
            query="topic", course_name=None, lesson_number=2
        )

    def test_execute_with_both_filters(self):
        """Test that execute passes both course and lesson filters"""
        mock_results = SearchResults(
            documents=["Content"],
            metadata=[{"course_title": "Python Programming", "lesson_number": 3}],
            distances=[0.1],
            error=None,
        )
        self.mock_vector_store.search.return_value = mock_results
        self.mock_vector_store.get_lesson_link.return_value = None

        # Execute with both filters
        result = self.tool.execute(
            query="advanced", course_name="Python Programming", lesson_number=3
        )

        # Verify search was called with both filters
        self.mock_vector_store.search.assert_called_once_with(
            query="advanced", course_name="Python Programming", lesson_number=3
        )

    def test_execute_with_error(self):
        """Test that execute handles vector store errors"""
        # Mock error results
        mock_results = SearchResults(
            documents=[],
            metadata=[],
            distances=[],
            error="Search error: connection failed",
        )
        self.mock_vector_store.search.return_value = mock_results

        # Execute
        result = self.tool.execute(query="test")

        # Verify error message returned
        self.assertEqual(result, "Search error: connection failed")

    def test_execute_populates_last_sources(self):
        """Test that execute populates last_sources attribute"""
        mock_results = SearchResults(
            documents=["Content 1", "Content 2"],
            metadata=[
                {"course_title": "Course A", "lesson_number": 1},
                {"course_title": "Course B", "lesson_number": 2},
            ],
            distances=[0.1, 0.2],
            error=None,
        )
        self.mock_vector_store.search.return_value = mock_results
        self.mock_vector_store.get_lesson_link.side_effect = [
            "http://example.com/1",
            "http://example.com/2",
        ]

        # Execute
        result = self.tool.execute(query="test")

        # Verify last_sources populated
        self.assertEqual(len(self.tool.last_sources), 2)
        self.assertEqual(self.tool.last_sources[0]["display"], "Course A - Lesson 1")
        self.assertEqual(self.tool.last_sources[0]["url"], "http://example.com/1")
        self.assertEqual(self.tool.last_sources[1]["display"], "Course B - Lesson 2")
        self.assertEqual(self.tool.last_sources[1]["url"], "http://example.com/2")

    def test_execute_without_lesson_number(self):
        """Test that execute handles chunks without lesson numbers"""
        mock_results = SearchResults(
            documents=["Content without lesson"],
            metadata=[{"course_title": "General Course", "chunk_index": 0}],
            distances=[0.1],
            error=None,
        )
        self.mock_vector_store.search.return_value = mock_results

        # Execute
        result = self.tool.execute(query="general")

        # Verify format without lesson number
        self.assertIn("[General Course]", result)
        self.assertIn("Content without lesson", result)
        # Verify no lesson link was requested
        self.mock_vector_store.get_lesson_link.assert_not_called()

    def test_execute_multiple_results_formatting(self):
        """Test that execute correctly formats multiple search results"""
        mock_results = SearchResults(
            documents=["First content", "Second content"],
            metadata=[
                {"course_title": "Course A", "lesson_number": 1},
                {"course_title": "Course A", "lesson_number": 2},
            ],
            distances=[0.1, 0.2],
            error=None,
        )
        self.mock_vector_store.search.return_value = mock_results
        self.mock_vector_store.get_lesson_link.return_value = None

        # Execute
        result = self.tool.execute(query="multiple")

        # Verify both results included
        self.assertIn("First content", result)
        self.assertIn("Second content", result)
        # Verify separator between results
        self.assertIn("\n\n", result)

    def test_get_tool_definition(self):
        """Test that tool definition is correctly structured"""
        definition = self.tool.get_tool_definition()

        # Verify required fields
        self.assertEqual(definition["name"], "search_course_content")
        self.assertIn("description", definition)
        self.assertIn("input_schema", definition)

        # Verify input schema structure
        schema = definition["input_schema"]
        self.assertEqual(schema["type"], "object")
        self.assertIn("properties", schema)
        self.assertIn("required", schema)

        # Verify required parameters
        self.assertIn("query", schema["required"])
        self.assertNotIn("course_name", schema["required"])
        self.assertNotIn("lesson_number", schema["required"])


if __name__ == "__main__":
    unittest.main()
