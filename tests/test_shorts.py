"""Tests for the experimental shorts package (src.shorts).

Covers the chapter guard, the happy path (with the LLM call mocked), and the
invariant that the shorts machinery no longer lives in the core modules.
"""
# Let Python locate the source code
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from unittest.mock import patch, MagicMock
from datetime import timedelta

from src.youtube_video import YouTubeVideo
from src.shorts import create_shorts_by_chapters
from src.shorts.generator import rework_transcript_to_sentences, create_shorts_script


def _make_mock_video(transcript=None, chapters=None, title="Test Video", channel="Test Channel"):
    """Build a YouTubeVideo mock with the attributes the shorts functions need."""
    video = MagicMock(spec=YouTubeVideo)
    video.url = "https://www.youtube.com/watch?v=test"
    video.title = title
    video.channel = channel
    video.transcript = transcript
    video.chapters = chapters
    video.chapters_available = chapters is not None
    return video


class TestShortsGuard(unittest.TestCase):
    """The chapter guard that fixes the known chapter-less crash."""

    def test_raises_on_no_chapters(self):
        transcript = [{"text": "hello", "timestamp": timedelta(0)}]
        video = _make_mock_video(transcript=transcript, chapters=None)
        with self.assertRaises(ValueError) as ctx:
            create_shorts_by_chapters(video=video)
        self.assertIn("no chapter markers", str(ctx.exception))
        self.assertIn("summarize_entire_video", str(ctx.exception))

    def test_raises_on_no_transcript(self):
        video = _make_mock_video(
            transcript=None, chapters=[{"timestamp": "0:00", "content": "Intro"}]
        )
        with self.assertRaises(ValueError):
            create_shorts_by_chapters(video=video)


class TestShortsHappyPath(unittest.TestCase):
    """Happy path with the LLM dispatcher mocked."""

    @patch("src.shorts.generator._chat")
    def test_returns_list_of_scripts(self, mock_chat):
        mock_chat.return_value = "Hook line. Body. CTA."
        transcript = [
            {"text": "intro text", "timestamp": timedelta(0), "start": "0:00"},
            {"text": "chapter 1 text", "timestamp": timedelta(seconds=60), "start": "1:00"},
        ]
        chapters = [
            {"timestamp": "0:00", "content": "Intro"},
            {"timestamp": "1:00", "content": "Chapter 1"},
        ]
        video = _make_mock_video(transcript=transcript, chapters=chapters)

        result = create_shorts_by_chapters(video=video)

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["heading"], "Intro")
        self.assertEqual(result[0]["script"], "Hook line. Body. CTA.")
        # Two LLM calls per chapter: rework_transcript_to_sentences + create_shorts_script.
        self.assertEqual(mock_chat.call_count, 4)


class TestShortsScriptUsesHeavyModel(unittest.TestCase):
    """create_shorts_script must keep using model_heavy (preserved behaviour)."""

    @patch("src.shorts.generator._chat")
    def test_create_shorts_script_uses_model_heavy(self, mock_chat):
        from src.config_loader import LLMSettings

        llm = LLMSettings(
            provider="ollama",
            base_url="http://localhost:11434",
            model="small-model",
            model_heavy="heavy-model",
            api_key=None,
        )
        create_shorts_script("some transcript", llm=llm)

        _, kwargs = mock_chat.call_args
        self.assertEqual(kwargs["model"], "heavy-model")


class TestOldPathsGone(unittest.TestCase):
    """The shorts machinery must no longer live in the core modules."""

    def test_core_no_longer_exposes_shorts(self):
        import src.transcribe_summarize as ts

        self.assertFalse(hasattr(ts, "create_shorts_by_chapters"))

    def test_gpt_functions_no_longer_exposes_prompt_helpers(self):
        import src.gpt_functions as gpt

        self.assertFalse(hasattr(gpt, "rework_transcript_to_sentences"))
        self.assertFalse(hasattr(gpt, "create_shorts_script"))
        # The core summary helpers must remain.
        self.assertTrue(hasattr(gpt, "get_chapter_summary"))
        self.assertTrue(hasattr(gpt, "get_whole_transcript_summary"))
        self.assertTrue(hasattr(gpt, "get_one_sentence_summary"))

    def test_prompt_helpers_live_only_in_shorts_generator(self):
        import src.shorts.generator as gen

        self.assertTrue(hasattr(gen, "rework_transcript_to_sentences"))
        self.assertTrue(hasattr(gen, "create_shorts_script"))
        self.assertTrue(hasattr(gen, "create_shorts_by_chapters"))


if __name__ == '__main__':
    unittest.main()
