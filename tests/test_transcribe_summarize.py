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


from src.transcribe_summarize import YouTubeVideo, YouTubeTranscribeSummarize

class Test_YouTubeVideo_Init(unittest.TestCase):
    def test_init(self):
        video = YouTubeVideo("https://www.youtube.com/watch?v=9bZkp7q19f0")
        self.assertEqual(video.url, "https://www.youtube.com/watch?v=9bZkp7q19f0")
    
    def test_init_podcast(self):
        video = YouTubeVideo("https://www.youtube.com/watch?v=X4DpDM9jmqo")
        self.assertEqual(video.url, "https://www.youtube.com/watch?v=X4DpDM9jmqo")

class Test_YouTubeVideo_GetMetadata(unittest.TestCase):
    def test_get_metadata(self):
        video = YouTubeVideo("https://www.youtube.com/watch?v=X4DpDM9jmqo")
        metadata = video._get_metadata()
        self.assertIsInstance(metadata, BeautifulSoup)
    
class Test_YouTubeVideo_GetMetadata(unittest.TestCase):
    def test_get_metadata(self):
        video = YouTubeVideo("https://www.youtube.com/watch?v=X4DpDM9jmqo")
        metadata = video._get_metadata()
        self.assertIsInstance(metadata, BeautifulSoup)

class Test_YouTubeVideo_GetTitle(unittest.TestCase):
    def test_get_title(self):
        video = YouTubeVideo("https://www.youtube.com/watch?v=X4DpDM9jmqo")
        video.soup = video._get_metadata()
        title = video._get_title()
        self.assertIsInstance(title, str)
        self.assertNotEqual(title, "Title not found")

class Test_YouTubeVideo_GetChannel(unittest.TestCase):
    def test_get_channel(self):
        video = YouTubeVideo("https://www.youtube.com/watch?v=X4DpDM9jmqo")
        video.soup = video._get_metadata()
        channel = video._get_channel()
        self.assertIsInstance(channel, str)
        self.assertNotEqual(channel, "Channel name not found")

class Test_YouTubeVideo_GetDuration(unittest.TestCase):
    def test_get_duration(self):
        video = YouTubeVideo("https://www.youtube.com/watch?v=X4DpDM9jmqo")
        video.soup = video._get_metadata()
        duration = video._get_duration()
        self.assertIsInstance(duration, timedelta)
        self.assertNotEqual(duration, "Duration not found")

class Test_YouTubeVideo_GetDescription(unittest.TestCase):
    def test_get_description(self):
        video = YouTubeVideo("https://www.youtube.com/watch?v=X4DpDM9jmqo")
        video.soup = video._get_metadata()
        description = video._get_description()
        self.assertIsInstance(description, str)
        self.assertNotEqual(description, None)

    if __name__ == '__main__':
        unittest.main()

if __name__ == '__main__':
    unittest.main()