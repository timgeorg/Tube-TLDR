# 
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

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
# User-defined Imports
from src.transcribe_summarize import YouTubeTranscribeSummarize
from src.youtube_video import YouTubeVideo


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

class Test_YouTubeVideo_GetTranscript(unittest.TestCase):
    def test_get_transcript(self):
        video = YouTubeVideo("https://www.youtube.com/watch?v=X4DpDM9jmqo")
        # TODO
    
class Test_YouTubeTranscribeSummarize_GetOutline(unittest.TestCase):
    def test_get_chapter_timestamps(self):
        video = YouTubeTranscribeSummarize("https://www.youtube.com/watch?v=X4DpDM9jmqo")
        video.get_data()
        outline = video.get_outline(video.description)
        print(outline)

        expected_output = [
        {"timestamp": "0:00", "content": "Intro"},
        {"timestamp": "1:20", "content": "Gibt es Delfine die intensiven Kontakt zu Menschen suchen?"},
        {"timestamp": "6:00", "content": "Wie viel Fisch darf ich essen, damit es noch nachhaltig ist?"},
        {"timestamp": "23:00", "content": "Kann man mit einer Ober-Fanggrenze dafür sorgen, dass sich unsere Meere regenerieren?"},
        {"timestamp": "30:00", "content": "Bei welchen Themen im Umweltschutz gibt es keine Ausreden?"},
        {"timestamp": "43:00", "content": "Warum ist es trotz der hohen Kosten und geringer Erfolgschance so wichtig, zu versuchen jedes einzelne Tier zu retten?"},
        {"timestamp": "50:00", "content": "Was läuft aktuell politisch und gesellschaftlich falsch?"},
        {"timestamp": "1:20:00", "content": "Wie bist du vom Angler und Aquariums-Chef zu dem Robert geworden, der du heute bist?"},
        {"timestamp": "1:41:00", "content": "Wie fandest du die Baby-Delfin Aktion von Inscope21?"},
        {"timestamp": "1:44:00", "content": "Warum kann man Wale beim Abnoetauchen besser beobachten?"},
        {"timestamp": "1:54:00", "content": "Wie ist das Gefühl von den größten Säugetieren der Welt, wahrgenommen zu werden?"},
        {"timestamp": "2:09:30", "content": "Wird man es schaffen, Delfine und Wale zu verstehen?"},
        {"timestamp": "2:23:00", "content": "Wie kann man selber tun, um den Tieren die in Gefangenschaft leben, zu helfen?"},
        {"timestamp": "2:30:00", "content": "Warum sind Wale so viel emphatischer als Menschen?"},
        {"timestamp": "2:53:00", "content": "Haben Wale Charakterunterschiede?"},
        {"timestamp": "3:02:00", "content": "Welche Erlebnisse auf deinen Reisen waren für dich besonders einprägsam?"},
        {"timestamp": "3:09:00", "content": "Wie stressig ist es das ganze Jahr auf Expeditionen zu sein?"},
        {"timestamp": "3:23:15", "content": "Warum möchte niemand für Umweltschutz bezahlen und wie finanzierst du dich?"},
        {"timestamp": "3:44:00", "content": "Würdest du nochmal Biologie studieren?"}
        ]


if __name__ == '__main__':
    unittest.main()