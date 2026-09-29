# Let Python locate the source code
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from unittest.mock import patch, MagicMock
from datetime import timedelta

from src.youtube_video import YouTubeVideo
from src.transcribe_summarize import (
    YouTubeTranscribeSummarize,
    summary_by_chapters,
    summary_entire_video,
    summary_in_one_sentence,
    _require_transcript,
)


def _make_mock_video(transcript=None, chapters=None, title="Test Video", channel="Test Channel"):
    """Build a YouTubeVideo mock with the attributes the summary functions need."""
    video = MagicMock(spec=YouTubeVideo)
    video.url = "https://www.youtube.com/watch?v=test"
    video.title = title
    video.channel = channel
    video.transcript = transcript
    video.chapters = chapters
    video.chapters_available = chapters is not None
    return video


class TestRequireTranscript(unittest.TestCase):
    """Tests for the _require_transcript guard."""

    def test_raises_on_none_transcript(self):
        video = _make_mock_video(transcript=None)
        with self.assertRaises(ValueError) as ctx:
            _require_transcript(video)
        self.assertIn("No transcript available", str(ctx.exception))

    def test_raises_on_empty_transcript(self):
        video = _make_mock_video(transcript=[])
        with self.assertRaises(ValueError):
            _require_transcript(video)

    def test_passes_with_transcript(self):
        video = _make_mock_video(transcript=[{"text": "hello", "timestamp": timedelta(0)}])
        # Should not raise
        _require_transcript(video)


class TestSummaryByChapters(unittest.TestCase):
    """Tests for summary_by_chapters."""

    def test_raises_on_no_transcript(self):
        video = _make_mock_video(transcript=None, chapters=[{"timestamp": "0:00", "content": "Intro"}])
        with self.assertRaises(ValueError):
            summary_by_chapters(video=video)

    def test_raises_on_no_chapters(self):
        transcript = [{"text": "hello", "timestamp": timedelta(0)}]
        video = _make_mock_video(transcript=transcript, chapters=None)
        with self.assertRaises(ValueError) as ctx:
            summary_by_chapters(video=video)
        self.assertIn("no chapter markers", str(ctx.exception))

    @patch("src.transcribe_summarize.gpt.get_chapter_summary")
    def test_returns_chapter_summaries(self, mock_gpt):
        mock_gpt.return_value = "Summary of chapter"
        transcript = [
            {"text": "intro text", "timestamp": timedelta(0)},
            {"text": "chapter 1 text", "timestamp": timedelta(seconds=60)},
        ]
        chapters = [
            {"timestamp": "0:00", "content": "Intro"},
            {"timestamp": "1:00", "content": "Chapter 1"},
        ]
        video = _make_mock_video(transcript=transcript, chapters=chapters)

        result = summary_by_chapters(video=video)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], "Summary of chapter")


class TestSummaryEntireVideo(unittest.TestCase):
    """Tests for summary_entire_video."""

    def test_raises_on_no_transcript(self):
        video = _make_mock_video(transcript=None)
        with self.assertRaises(ValueError):
            summary_entire_video(video=video)

    @patch("src.transcribe_summarize.gpt.get_whole_transcript_summary")
    def test_returns_summary(self, mock_gpt):
        mock_gpt.return_value = "Whole video summary"
        transcript = [
            {"text": "hello", "timestamp": timedelta(0)},
            {"text": "world", "timestamp": timedelta(seconds=5)},
        ]
        video = _make_mock_video(transcript=transcript)

        result = summary_entire_video(video=video)
        self.assertEqual(result, "Whole video summary")
        mock_gpt.assert_called_once()


class TestSummaryOneSentence(unittest.TestCase):
    """Tests for summary_in_one_sentence."""

    def test_raises_on_no_transcript(self):
        video = _make_mock_video(transcript=None)
        with self.assertRaises(ValueError):
            summary_in_one_sentence(video=video)

    @patch("src.transcribe_summarize.gpt.get_one_sentence_summary")
    def test_returns_one_sentence(self, mock_gpt):
        mock_gpt.return_value = "One sentence summary."
        transcript = [{"text": "hello", "timestamp": timedelta(0)}]
        video = _make_mock_video(transcript=transcript, title="My Title")

        result = summary_in_one_sentence(video=video)
        self.assertEqual(result, "One sentence summary.")
        mock_gpt.assert_called_once()


class TestConvertTimestampsToTimedelta(unittest.TestCase):
    """Tests for YouTubeTranscribeSummarize.convert_timestamps_to_timedelta."""

    def test_convert_mmss(self):
        video = _make_mock_video()
        obj = YouTubeTranscribeSummarize(youtube_video=video)
        chapters = [{"timestamp": "1:30", "content": "Chapter 1"}]
        result = obj.convert_timestamps_to_timedelta(chapters)
        self.assertEqual(result[0]["timestamp"], timedelta(minutes=1, seconds=30))
        self.assertEqual(result[0]["timestr"], "1:30")

    def test_convert_hhmmss(self):
        video = _make_mock_video()
        obj = YouTubeTranscribeSummarize(youtube_video=video)
        chapters = [{"timestamp": "1:02:30", "content": "Chapter 2"}]
        result = obj.convert_timestamps_to_timedelta(chapters)
        self.assertEqual(result[0]["timestamp"], timedelta(hours=1, minutes=2, seconds=30))

    def test_convert_invalid_format(self):
        video = _make_mock_video()
        obj = YouTubeTranscribeSummarize(youtube_video=video)
        chapters = [{"timestamp": "invalid", "content": "Bad"}]
        with self.assertRaises(ValueError):
            obj.convert_timestamps_to_timedelta(chapters)


if __name__ == '__main__':
    unittest.main()
