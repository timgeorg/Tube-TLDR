# Let Python locate the source code
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
# Testing
import unittest
# User-defined Imports
from src.youtube_video import YouTubeVideo
from src.logger import Logger
import unittest
from unittest.mock import patch, MagicMock


# Mock the YouTubeVideo class
class MockYouTubeVideo(Logger):
    def __init__(self):
        self.logger = self.create_logger(name=self.__class__.__name__) # Mock the logger
        self.chapters_available = True
    
    def _extract_chapters(description):
        return YouTubeVideo._extract_chapters(description)
    

class Test_YouTubeVideo_extract_chapters(unittest.TestCase):

    def setUp(self):
        self.mock = MockYouTubeVideo()
        super().setUp()

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
        self.mock.description = description_example
        function_output = self.mock._extract_chapters()
        self.assertEqual(function_output, expected_outline)


    def test_extract_chapters_with_hours(self):
        description_example = """
            0:00 Introduction
            0:10 Chapter 1: Getting Started
            0:20 Chapter 2: Basic Concepts
            0:30 Chapter 3: Advanced Techniques
            0:40 Chapter 4: Expert Tips
            0:50 Chapter 5: Common Pitfalls
            1:00:00 Chapter 6: Best Practices
            1:10:00 Chapter 7: Advanced Topics
            1:20:00 Chapter 8: Expert Insights
            1:30:00 Conclusion
        """
        expected_outline = [
            {"timestamp": "0:00", "content": "Introduction"},
            {"timestamp": "0:10", "content": "Chapter 1: Getting Started"},
            {"timestamp": "0:20", "content": "Chapter 2: Basic Concepts"},
            {"timestamp": "0:30", "content": "Chapter 3: Advanced Techniques"},
            {"timestamp": "0:40", "content": "Chapter 4: Expert Tips"},
            {"timestamp": "0:50", "content": "Chapter 5: Common Pitfalls"},
            {"timestamp": "1:00:00", "content": "Chapter 6: Best Practices"},
            {"timestamp": "1:10:00", "content": "Chapter 7: Advanced Topics"},
            {"timestamp": "1:20:00", "content": "Chapter 8: Expert Insights"},
            {"timestamp": "1:30:00", "content": "Conclusion"}
        ]
        mock = MockYouTubeVideo()
        mock.description = description_example
        function_output = mock._extract_chapters()
        self.assertEqual(function_output, expected_outline)
        

    def test_extract_chapters_real_example_TimGabel_RML(self):
        description_example = """
            ► Timestamps
            0:00 Intro
            1:20 Gibt es Delfine die intensiven Kontakt zu Menschen suchen?
            6:00 Wie viel Fisch darf ich essen, damit es noch nachhaltig ist?
            23:00 Kann man mit einer Ober-Fanggrenze dafür sorgen, dass sich unsere Meere regenerieren?
            30:00 Bei welchen Themen im Umweltschutz gibt es keine Ausreden?
            43:00 Warum ist es trotz der hohen Kosten und geringer Erfolgschance so wichtig , zu versuchen jedes einzelne Tier zu retten?
            50:00 Was läuft aktuell politisch und gesellschaftlich falsch? 
            1:20:00 Wie bist du vom Angler und Aquariums-Chef zu dem Robert geworden, der du heute bist?
            1:41:00 Wie fandest du die Baby-Delfin Aktion von Inscope21?
            1:44:00 Warum kann man Wale beim Abnoetauchen besser beobachten?
            1:54:00 Wie ist das Gefühl von den größten Säugetieren der Welt, wahrgenommen zu werden?
            2:09:30 Wird man es schaffen, Delfine und Wale zu verstehen?
            2:23:00 Wie kann man selber tun, um den Tieren die in Gefangenschaft leben, zu helfen?
            2:30:00 Warum sind Wale so viel emphatischer als Menschen?
            2:53:00 Haben Wale Charakterunterschiede?
            3:02:00 Welche Erlebnisse auf deinen Reisen waren für dich besonders einprägsam?
            3:09:00 Wie stressig ist es das ganze Jahr auf Expeditionen zu sein? 
            3:23:15 Warum möchte niemand für Umweltschutz bezahlen und wie finanzierst du dich?
            3:44:00 Würdest du nochmal Biologie studieren?
        """
        expected_output = [
            {"timestamp": "0:00", "content": "Intro"},
            {"timestamp": "1:20", "content": "Gibt es Delfine die intensiven Kontakt zu Menschen suchen?"},
            {"timestamp": "6:00", "content": "Wie viel Fisch darf ich essen, damit es noch nachhaltig ist?"},
            {"timestamp": "23:00", "content": "Kann man mit einer Ober-Fanggrenze dafür sorgen, dass sich unsere Meere regenerieren?"},
            {"timestamp": "30:00", "content": "Bei welchen Themen im Umweltschutz gibt es keine Ausreden?"},
            {"timestamp": "43:00", "content": "Warum ist es trotz der hohen Kosten und geringer Erfolgschance so wichtig , zu versuchen jedes einzelne Tier zu retten?"},
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
        mock = MockYouTubeVideo()
        mock.description = description_example
        function_output = mock._extract_chapters()
        self.assertEqual(function_output, expected_output)

    def test_extract_chapters_real_example_TimSturmer_Analogicas(self):
        description_example = """
            Visit: Revelaciones Analògicas // Selbstportrait im Studio – Vom Negativ bis zum Abzug
            00:00 Willkommen im Studio
            00:41 Miguel’s Vision & das Setup 
            07:48 Meine Selbst-Portrait-Session 
            10:01 Filmentwicklung – Die analoge Küche
            13:17 Das Negativ & Darkroom-Printing
            19:35 Ein perfektes Portrait
            20:39 Der krönende Abschluss, so geht’s weiter! 
        """
        expected_output = [
            {"timestamp": "00:00", "content": "Willkommen im Studio"},
            {"timestamp": "00:41", "content": "Miguel’s Vision & das Setup"},
            {"timestamp": "07:48", "content": "Meine Selbst-Portrait-Session"},
            {"timestamp": "10:01", "content": "Filmentwicklung – Die analoge Küche"},
            {"timestamp": "13:17", "content": "Das Negativ & Darkroom-Printing"},
            {"timestamp": "19:35", "content": "Ein perfektes Portrait"},
            {"timestamp": "20:39", "content": "Der krönende Abschluss, so geht’s weiter!"}
        ]
        mock = MockYouTubeVideo()
        mock.description = description_example
        function_output = mock._extract_chapters()
        self.assertEqual(function_output, expected_output)

    def test_extract_chapters_no_timestamps(self):
        self.mock.chapters_available = False
        expected_output = None
        function_output = self.mock._extract_chapters()
        self.assertEqual(function_output, expected_output)

    def test_extract_chapters_real_example_YCombinator(self):
        description_example = """
            Apply for a YC Summer Fellows Grant: https://events.ycombinator.com/summer-fellows\n\n
            Technical skills build startups—but oftentimes, people skills can save them. 
            So how do you navigate the disagreements and conflict that inevitably arise with a co-founder? 
            In this episode of the Lightcone, our hosts share what they've learned for managing these critical, 
            yet often overlooked challenges, offering advice on how to handle the messy realities that go beyond building.\n\n
            Chapters (Powered by https://bit.ly/chapterme-yc) -\n00:00 Intro\n01:09 Why you should listen to this episode! \n
            02:25 Harj’s experience with Patrick Collison of Stripe\n06:39 Hard lessons Garry learned from Posterous \n
            12:52 Authoritative vs authoritarian \n15:46 Startup pressures lead to self discovery \n
            19:47 The importance of conflict resolution skills\n24:24 The concept of “over the net”\n
            27:15 The cultures you come from (work and personal) matter a lot\n34:53 Founders should get outside help  
            \n36:07 Why you should still find a co-founder despite the challenges\n39:53 Outro + YC Summer Fellow Grants
        """
        expected_output = [
            {"timestamp": "00:00", "content": "Intro"},
            {"timestamp": "01:09", "content": "Why you should listen to this episode!"},
            {"timestamp": "02:25", "content": "Harj’s experience with Patrick Collison of Stripe"},
            {"timestamp": "06:39", "content": "Hard lessons Garry learned from Posterous"},
            {"timestamp": "12:52", "content": "Authoritative vs authoritarian"},
            {"timestamp": "15:46", "content": "Startup pressures lead to self discovery"},
            {"timestamp": "19:47", "content": "The importance of conflict resolution skills"},
            {"timestamp": "24:24", "content": "The concept of “over the net”"},
            {"timestamp": "27:15", "content": "The cultures you come from (work and personal) matter a lot"},
            {"timestamp": "34:53", "content": "Founders should get outside help"},
            {"timestamp": "36:07", "content": 'Why you should still find a co-founder despite the challenges'},
            {"timestamp": "39:53", "content": 'Outro + YC Summer Fellow Grants'}
        ]
        mock = MockYouTubeVideo()
        mock.description = description_example
        function_output = mock._extract_chapters()
        self.assertEqual(function_output, expected_output)


class Test_YouTubeVideo_get_transcript(unittest.TestCase):
    def setUp(self):
        self.video = YouTubeVideo("https://youtube.com/watch?v=dQw4w9WgXcQ")
        self.video.logger = MagicMock()
        self.video.soup = MagicMock()
        self.video.description = "desc"
        self.video.chapters_available = False

    @patch("src.youtube_video.YouTubeTranscriptApi")
    def test_get_transcript_success(self, mock_api):
        # Mock transcript data
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
        mock_api.list_transcripts.return_value = mock_transcript_list

        result = self.video._get_transcript(languages=("en",))
        self.assertIsInstance(result, list)
        self.assertEqual(result[0]['text'], 'Hello')
        self.assertIn('timestamp', result[0])
        self.assertEqual(result[1]['text'], 'World')
        self.assertIn('timestamp', result[1])

    @patch("src.youtube_video.YouTubeTranscriptApi")
    def test_get_transcript_no_data(self, mock_api):
        mock_transcript = MagicMock()
        mock_fetched = MagicMock()
        mock_fetched.to_raw_data.return_value = []
        mock_transcript.fetch.return_value = mock_fetched
        mock_transcript_list = MagicMock()
        mock_transcript_list.find_generated_transcript.return_value = mock_transcript
        mock_api.list_transcripts.return_value = mock_transcript_list

        result = self.video._get_transcript(languages=("en",))
        self.assertIsNone(result)

    @patch("src.youtube_video.YouTubeTranscriptApi")
    def test_get_transcript_exception(self, mock_api):
        mock_api.list_transcripts.side_effect = Exception("API error")
        result = self.video._get_transcript(languages=("en",))
        self.assertIsNone(result)

    @patch("src.youtube_video.YouTubeTranscriptApi")
    def test_get_transcript_falls_back_to_manual(self, mock_api):
        transcript_data = [
            {'start': 0.0, 'duration': 5.0, 'text': 'Manual'},
        ]
        mock_fetched = MagicMock()
        mock_fetched.to_raw_data.return_value = transcript_data
        mock_manual_transcript = MagicMock()
        mock_manual_transcript.fetch.return_value = mock_fetched

        mock_transcript_list = MagicMock()
        mock_transcript_list.find_generated_transcript.side_effect = Exception("No generated transcript")
        mock_transcript_list.find_manually_created_transcript.return_value = mock_manual_transcript
        mock_api.list_transcripts.return_value = mock_transcript_list

        result = self.video._get_transcript(languages=("en",))
        self.assertIsInstance(result, list)
        self.assertEqual(result[0]['text'], 'Manual')
        self.assertIn('timestamp', result[0])

    @patch("src.youtube_video.YouTubeTranscriptApi")
    def test_get_transcript_any_fallback_prefers_generated(self, mock_api):
        mock_transcript_list = MagicMock()
        mock_transcript_list.find_generated_transcript.side_effect = Exception("No preferred generated")
        mock_transcript_list.find_manually_created_transcript.side_effect = Exception("No preferred manual")

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

        mock_transcript_list.__iter__.return_value = iter([mock_generated, mock_manual])
        mock_api.list_transcripts.return_value = mock_transcript_list

        result = self.video._get_transcript(languages=("en",))
        self.assertIsInstance(result, list)
        self.assertEqual(result[0]['text'], 'Generated')
        self.assertIn('timestamp', result[0])
        
    @patch("src.youtube_video.YouTubeTranscriptApi")
    def test_get_transcript_debug_output(self, mock_api):
        transcript_data = [{'start': 0.0, 'duration': 1.0, 'text': '[Music]'}]
        mock_fetched = MagicMock()
        mock_fetched.to_raw_data.return_value = transcript_data
        mock_transcript = MagicMock()
        mock_transcript.fetch.return_value = mock_fetched
        mock_transcript_list = MagicMock()
        mock_transcript_list.find_generated_transcript.return_value = mock_transcript
        mock_api.list_transcripts.return_value = mock_transcript_list

        video = YouTubeVideo("https://youtube.com/watch?v=dQw4w9WgXcQ")
        result = video._get_transcript(languages=("en",))
        print("DEBUG transcript result:", result)
        self.assertIsInstance(result, list)
        self.assertEqual(result[0]['text'], '[Music]')


if __name__ == '__main__':
    unittest.main()