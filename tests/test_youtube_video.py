# Let Python locate the source code
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from unittest.mock import patch, MagicMock
from datetime import timedelta

from src.youtube_video import YouTubeVideo


class TestExtractVideoId(unittest.TestCase):
    """Tests for YouTubeVideo._extract_video_id."""

    def setUp(self):
        self.video = YouTubeVideo.__new__(YouTubeVideo)

    def test_watch_url(self):
        self.assertEqual(self.video._extract_video_id("https://www.youtube.com/watch?v=_FBivfgOvuE"), "_FBivfgOvuE")

    def test_watch_url_with_trailing_amp(self):
        self.assertEqual(self.video._extract_video_id("https://www.youtube.com/watch?v=_FBivfgOvuE&"), "_FBivfgOvuE")

    def test_watch_url_with_extra_params(self):
        self.assertEqual(self.video._extract_video_id("https://www.youtube.com/watch?v=_FBivfgOvuE&t=42s"), "_FBivfgOvuE")

    def test_short_url(self):
        self.assertEqual(self.video._extract_video_id("https://youtu.be/_FBivfgOvuE"), "_FBivfgOvuE")

    def test_embed_url(self):
        self.assertEqual(self.video._extract_video_id("https://www.youtube.com/embed/_FBivfgOvuE"), "_FBivfgOvuE")

    def test_shorts_url(self):
        self.assertEqual(self.video._extract_video_id("https://www.youtube.com/shorts/_FBivfgOvuE"), "_FBivfgOvuE")


class TestExtractChapters(unittest.TestCase):
    """Tests for YouTubeVideo._extract_chapters (pure logic, no network)."""

    def _make_video_with_description(self, description, chapters_available=True):
        video = YouTubeVideo.__new__(YouTubeVideo)
        video.description = description
        video.chapters_available = chapters_available
        video.logger = MagicMock()
        return video

    def test_extract_chapters_simple(self):
        description = """
            0:00 Introduction
            1:00 Chapter 1
            2:00 Chapter 2
            3:00 Conclusion
        """
        video = self._make_video_with_description(description)
        result = video._extract_chapters()
        self.assertEqual(result, [
            {"timestamp": "0:00", "content": "Introduction"},
            {"timestamp": "1:00", "content": "Chapter 1"},
            {"timestamp": "2:00", "content": "Chapter 2"},
            {"timestamp": "3:00", "content": "Conclusion"},
        ])

    def test_extract_chapters_with_hours(self):
        description = """
            0:00 Introduction
            1:00:00 Chapter 6
            1:30:00 Conclusion
        """
        video = self._make_video_with_description(description)
        result = video._extract_chapters()
        self.assertEqual(result, [
            {"timestamp": "0:00", "content": "Introduction"},
            {"timestamp": "1:00:00", "content": "Chapter 6"},
            {"timestamp": "1:30:00", "content": "Conclusion"},
        ])

    def test_extract_chapters_no_timestamps(self):
        video = self._make_video_with_description("No timestamps here", chapters_available=False)
        result = video._extract_chapters()
        self.assertIsNone(result)

    def test_extract_chapters_real_yc_example(self):
        description = """
            Chapters (Powered by https://bit.ly/chapterme-yc) -\n00:00 Intro\n01:09 Why you should listen\n
            02:25 Harj's experience\n06:39 Hard lessons\n12:52 Authoritative vs authoritarian\n
        """
        video = self._make_video_with_description(description)
        result = video._extract_chapters()
        self.assertIsInstance(result, list)
        self.assertEqual(result[0], {"timestamp": "00:00", "content": "Intro"})
        self.assertEqual(result[1], {"timestamp": "01:09", "content": "Why you should listen"})


class TestGetTranscript(unittest.TestCase):
    """Tests for YouTubeVideo._get_transcript with mocked Ollama API."""

    def setUp(self):
        self.video = YouTubeVideo("https://youtube.com/watch?v=dQw4w9WgXcQ")
        self.video.logger = MagicMock()

    @patch("src.youtube_video.YouTubeTranscriptApi")
    def test_get_transcript_success(self, mock_api_class):
        transcript_data = [
            {'start': 0.0, 'duration': 5.0, 'text': 'Hello'},
            {'start': 5.0, 'duration': 4.0, 'text': 'World'}
        ]
        mock_fetched = MagicMock()
        mock_fetched.to_raw_data.return_value = transcript_data
        mock_transcript = MagicMock()
        mock_transcript.fetch.return_value = mock_fetched
        mock_transcript_list = MagicMock()
        mock_transcript_list.find_generated_transcript.return_value = mock_transcript

        mock_api_instance = MagicMock()
        mock_api_instance.list.return_value = mock_transcript_list
        mock_api_class.return_value = mock_api_instance

        result = self.video._get_transcript(languages=("en",))
        self.assertIsInstance(result, list)
        self.assertEqual(result[0]['text'], 'Hello')
        self.assertIn('timestamp', result[0])
        self.assertEqual(result[1]['text'], 'World')

    @patch("src.youtube_video.YouTubeTranscriptApi")
    def test_get_transcript_no_data(self, mock_api_class):
        mock_fetched = MagicMock()
        mock_fetched.to_raw_data.return_value = []
        mock_transcript = MagicMock()
        mock_transcript.fetch.return_value = mock_fetched
        mock_transcript_list = MagicMock()
        mock_transcript_list.find_generated_transcript.return_value = mock_transcript

        mock_api_instance = MagicMock()
        mock_api_instance.list.return_value = mock_transcript_list
        mock_api_class.return_value = mock_api_instance

        result = self.video._get_transcript(languages=("en",))
        self.assertIsNone(result)

    @patch("src.youtube_video.YouTubeTranscriptApi")
    def test_get_transcript_exception(self, mock_api_class):
        mock_api_instance = MagicMock()
        mock_api_instance.list.side_effect = Exception("API error")
        mock_api_class.return_value = mock_api_instance

        result = self.video._get_transcript(languages=("en",))
        self.assertIsNone(result)

    @patch("src.youtube_video.YouTubeTranscriptApi")
    def test_get_transcript_falls_back_to_manual(self, mock_api_class):
        transcript_data = [{'start': 0.0, 'duration': 5.0, 'text': 'Manual'}]
        mock_fetched = MagicMock()
        mock_fetched.to_raw_data.return_value = transcript_data
        mock_manual_transcript = MagicMock()
        mock_manual_transcript.fetch.return_value = mock_fetched

        mock_transcript_list = MagicMock()
        mock_transcript_list.find_generated_transcript.side_effect = Exception("No generated")
        mock_transcript_list.find_manually_created_transcript.return_value = mock_manual_transcript

        mock_api_instance = MagicMock()
        mock_api_instance.list.return_value = mock_transcript_list
        mock_api_class.return_value = mock_api_instance

        result = self.video._get_transcript(languages=("en",))
        self.assertIsInstance(result, list)
        self.assertEqual(result[0]['text'], 'Manual')

    @patch("src.youtube_video.YouTubeTranscriptApi")
    def test_get_transcript_any_fallback_prefers_generated(self, mock_api_class):
        mock_generated_fetched = MagicMock()
        mock_generated_fetched.to_raw_data.return_value = [{'start': 0.0, 'duration': 1.0, 'text': 'Generated'}]
        mock_generated = MagicMock()
        mock_generated.is_generated = True
        mock_generated.fetch.return_value = mock_generated_fetched

        mock_manual_fetched = MagicMock()
        mock_manual_fetched.to_raw_data.return_value = [{'start': 0.0, 'duration': 1.0, 'text': 'Manual'}]
        mock_manual = MagicMock()
        mock_manual.is_generated = False
        mock_manual.fetch.return_value = mock_manual_fetched

        mock_transcript_list = MagicMock()
        mock_transcript_list.find_generated_transcript.side_effect = Exception("No preferred generated")
        mock_transcript_list.find_manually_created_transcript.side_effect = Exception("No preferred manual")
        mock_transcript_list.__iter__.return_value = iter([mock_generated, mock_manual])

        mock_api_instance = MagicMock()
        mock_api_instance.list.return_value = mock_transcript_list
        mock_api_class.return_value = mock_api_instance

        result = self.video._get_transcript(languages=("en",))
        self.assertIsInstance(result, list)
        self.assertEqual(result[0]['text'], 'Generated')


if __name__ == '__main__':
    unittest.main()
