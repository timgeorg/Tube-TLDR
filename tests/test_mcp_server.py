# Let Python locate the source code
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import time
import unittest
from unittest.mock import MagicMock

import src.mcp_server as mcp_server
from src.mcp_server import _handle_call_tool, _TOOLS, TOOL_TIMEOUT_S


def _run(coro):
    """Drive a coroutine to completion without pytest-asyncio."""
    return asyncio.run(coro)


def _make_mock_video(title="Test Video", channel="Test Channel"):
    """Build a stand-in for a fetched YouTubeVideo (only the attrs _format_result reads)."""
    video = MagicMock()
    video.title = title
    video.channel = channel
    video.upload_date = "2026-01-01"
    video.url = "https://www.youtube.com/watch?v=test"
    return video


class _McpTestBase(unittest.TestCase):
    """Shared patching: stub the network fetch and the LLM summary functions."""

    def setUp(self):
        self._orig_fetch = mcp_server._fetch_video
        self._orig_timeout = mcp_server.TOOL_TIMEOUT_S
        self._orig_entire = mcp_server.ts.summary_entire_video
        self._orig_chapters = mcp_server.ts.summary_by_chapters
        self._orig_one = mcp_server.ts.summary_in_one_sentence

        self.video = _make_mock_video()
        mcp_server._fetch_video = lambda url, language: self.video

    def tearDown(self):
        mcp_server._fetch_video = self._orig_fetch
        mcp_server.TOOL_TIMEOUT_S = self._orig_timeout
        mcp_server.ts.summary_entire_video = self._orig_entire
        mcp_server.ts.summary_by_chapters = self._orig_chapters
        mcp_server.ts.summary_in_one_sentence = self._orig_one


class TestSuccessPath(_McpTestBase):
    def test_summarize_entire_video_returns_header(self):
        mcp_server.ts.summary_entire_video = lambda video, llm: "- point one\n- point two"

        result = _run(_handle_call_tool(
            "summarize_entire_video",
            {"url": "https://www.youtube.com/watch?v=test"},
        ))

        self.assertFalse(result.isError)
        text = result.content[0].text
        self.assertIn("## Test Video", text)
        self.assertIn("*by Test Channel*", text)
        self.assertIn("- point one", text)

    def test_summarize_one_sentence_returns_header(self):
        mcp_server.ts.summary_in_one_sentence = lambda video, llm: "One sentence."

        result = _run(_handle_call_tool(
            "summarize_one_sentence",
            {"url": "https://www.youtube.com/watch?v=test"},
        ))

        self.assertFalse(result.isError)
        self.assertIn("## Test Video", result.content[0].text)
        self.assertIn("One sentence.", result.content[0].text)


class TestErrorShapes(_McpTestBase):
    def test_failing_summary_is_error_not_success(self):
        def boom(video, llm):
            raise ValueError("llm exploded")

        mcp_server.ts.summary_entire_video = boom

        result = _run(_handle_call_tool(
            "summarize_entire_video",
            {"url": "https://www.youtube.com/watch?v=test"},
        ))

        # Must be a real MCP error, not a success whose text starts with "Error".
        self.assertTrue(result.isError)
        self.assertIn("Error summarizing", result.content[0].text)
        self.assertIn("llm exploded", result.content[0].text)

    def test_failing_fetch_is_error(self):
        def boom(url, language):
            raise RuntimeError("network down")

        mcp_server._fetch_video = boom

        result = _run(_handle_call_tool(
            "summarize_entire_video",
            {"url": "https://www.youtube.com/watch?v=test"},
        ))

        self.assertTrue(result.isError)
        self.assertIn("Error fetching video", result.content[0].text)

    def test_missing_url_is_error(self):
        result = _run(_handle_call_tool("summarize_entire_video", {}))

        self.assertTrue(result.isError)
        self.assertIn("'url' is required", result.content[0].text)

    def test_blank_url_is_error(self):
        result = _run(_handle_call_tool("summarize_entire_video", {"url": "   "}))

        self.assertTrue(result.isError)
        self.assertIn("'url' is required", result.content[0].text)

    def test_unknown_tool_is_error(self):
        result = _run(_handle_call_tool(
            "does_not_exist",
            {"url": "https://www.youtube.com/watch?v=test"},
        ))

        self.assertTrue(result.isError)
        self.assertIn("Unknown tool", result.content[0].text)


class TestTimeout(_McpTestBase):
    def test_summary_timeout_is_error(self):
        def slow(video, llm):
            time.sleep(0.3)
            return "too late"

        mcp_server.ts.summary_entire_video = slow
        mcp_server.TOOL_TIMEOUT_S = 0.05

        result = _run(_handle_call_tool(
            "summarize_entire_video",
            {"url": "https://www.youtube.com/watch?v=test"},
        ))

        self.assertTrue(result.isError)
        self.assertIn("timed out", result.content[0].text)

    def test_fetch_timeout_is_error(self):
        def slow_fetch(url, language):
            time.sleep(0.3)
            return self.video

        mcp_server._fetch_video = slow_fetch
        mcp_server.TOOL_TIMEOUT_S = 0.05

        result = _run(_handle_call_tool(
            "summarize_entire_video",
            {"url": "https://www.youtube.com/watch?v=test"},
        ))

        self.assertTrue(result.isError)
        self.assertIn("timed out", result.content[0].text)


class TestToolDefinitions(unittest.TestCase):
    def test_three_tools_with_annotations_and_titles(self):
        names = [t.name for t in _TOOLS]
        self.assertEqual(
            names,
            ["summarize_by_chapters", "summarize_entire_video", "summarize_one_sentence"],
        )
        for tool in _TOOLS:
            self.assertIsNotNone(tool.title)
            self.assertIsNotNone(tool.annotations)
            self.assertTrue(tool.annotations.readOnlyHint)
            self.assertTrue(tool.annotations.idempotentHint)
            self.assertTrue(tool.annotations.openWorldHint)

    def test_default_timeout_is_900(self):
        # Only assert the default when the env var is not set in this process.
        if "TUBE_TLDR_TOOL_TIMEOUT_S" not in os.environ:
            self.assertEqual(TOOL_TIMEOUT_S, 900.0)


if __name__ == "__main__":
    unittest.main()
