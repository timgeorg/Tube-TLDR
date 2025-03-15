import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
# Native Libraries
import os
import re
import sys
import json
import requests
from datetime import datetime, timedelta
# External Libraries
from bs4 import BeautifulSoup
from dotenv import load_dotenv # pip install python-dotenv
from youtube_transcript_api import YouTubeTranscriptApi
from openai import OpenAI # OR: from openai import AzureOpenAI

from src.youtube_video import YouTubeVideo
from Utilities.logger import Logger

# Mock the YouTubeVideo class
class MockYouTubeVideo(Logger):
    def __init__(self):
        self.logger = self.create_logger(name=self.__class__.__name__) # Mock the logger
    
    def _extract_chapters(description):
        return YouTubeVideo._extract_chapters(description)
    

class Test_YouTubeVideo_extract_chapters(unittest.TestCase):

    def test_extract_chapters(self):
        description_example = """
            0:00 Introduction
            1:00 Chapter 1
            2:00 Chapter 2
            3:00 Chapter 3
            4:00 Chapter 4
            5:00 Chapter 5
            6:00 Conclusion
        """
        expected_outline = [
            {"timestamp": "0:00", "content": "Introduction"},
            {"timestamp": "1:00", "content": "Chapter 1"},
            {"timestamp": "2:00", "content": "Chapter 2"},
            {"timestamp": "3:00", "content": "Chapter 3"},
            {"timestamp": "4:00", "content": "Chapter 4"},
            {"timestamp": "5:00", "content": "Chapter 5"},
            {"timestamp": "6:00", "content": "Conclusion"}
        ]
        mock = MockYouTubeVideo()
        mock.description = description_example
        function_output = mock._extract_chapters()
        self.assertEqual(function_output, expected_outline)

if __name__ == '__main__':
    unittest.main()