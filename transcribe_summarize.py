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

# User-defined Libraries
from src.youtube_video import YouTubeVideo
from Utilities.logger import Logger
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = Logger.create_logger(name=__name__)

class YouTubeTranscribeSummarize(YouTubeVideo):

    def __init__(self, url, api_key=os.getenv('OPENAI_API_KEY')):
        super().__init__(url)
        self.api_key = api_key

    def get_outline(self, description):

        client = OpenAI(api_key=self.api_key)

        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'user', 
                'content': 
                    'Convert the following youtube video description into a JSON list with "timestamp" and "topic" keys and values.\n \
                    Use this format: [{"timestamp": "00:00:00", "topic": "Introduction"}, {"timestamp": "00:01:30", "topic": "Chapter 1"}]\n \
                    Here is the Video Description with the timestamps shall be extracted \n\n' + description},
            ],
            temperature=0.2,
            # max_tokens=,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
            response_format={ "type": "json_object" }
        )

        result = response.choices[0].message.content
        result = result.replace("\n", "").rstrip().lstrip().replace("  ", "")

        try:
            result = json.loads(result)
            print(result)
            if not result["timestamps"]:
                self.logger.info(f"No outline found in description.")
                return None
            elif type(result["timestamps"]) == str:
                self.logger.info(f"No Outline found in description. Creating synthetic outline.")
                return None
            
            elif type(result["timestamps"]) == list:
                self.logger.info(f"Outline found in description. Returning outline.")
                return result
            else:
                self.logger.info(f"Outline found in description. Returning outline.")
                return result
        except Exception as e:
            self.logger.info(f"No outline found in description: {e}")
            return None


    def _convert_timestamps(self, result: dict) -> list:

        outlist = result["timestamps"]

        for item in outlist:
            time_parts = item["timestamp"].split(":")
            if len(time_parts) == 2:  # Format is "MM:SS"
                minutes, seconds = map(int, time_parts)
                item["timestamp"] = timedelta(minutes=minutes, seconds=seconds)
            elif len(time_parts) == 3:  # Format is "HH:MM:SS"
                hours, minutes, seconds = map(int, time_parts)
                item["timestamp"] = timedelta(hours=hours, minutes=minutes, seconds=seconds)
            else:
                raise ValueError(f"Unexpected timestamp format: {item['timestamp']}")

        return outlist


    def link_content_to_outline(self, content, outline):

        for item in outline:
            item["content"] = []
            start_time = item["timestamp"]
            end_time = outline[outline.index(item) + 1]["timestamp"] if outline.index(item) + 1 < len(outline) else None
            
            for entry in content:
                if end_time:
                    if start_time <= entry["timestamp"] < end_time:
                        item["content"].append(entry["text"])
                else:
                    if entry["timestamp"] >= start_time:
                        item["content"].append(entry["text"])

        for item in outline:
            item["content"] = " ".join(item["content"])

        return outline


    def link_transcript_without_outline(self, content):

        # get max length of content
        content_length = content[-1]["timestamp"] # get timedelta object of last entry

        total_duration = content_length.total_seconds() / 60  # Convert total duration to minutes

        # Determine chunk length based on total duration
        if total_duration <= 15:
            chunk_length = timedelta(minutes=total_duration)
        elif 15 < total_duration <= 45:
            chunk_length = timedelta(minutes=5)
        elif 45 < total_duration <= 90:
            chunk_length = timedelta(minutes=10)
        else:
            chunk_length = timedelta(minutes=15)
            
        sections = []
        section = {"timestamp": content[0]["timestamp"], "content": []}

        for entry in content:
            if entry["timestamp"] < section["timestamp"] + chunk_length:
                section["content"].append(entry["text"])
            else:
                section["content"] = " ".join(section["content"])
                sections.append(section)
                section = {"timestamp": entry["timestamp"], "content": [entry["text"]]}

        section["content"] = " ".join(section["content"])
        sections.append(section)

        for section in sections:
            section["topic"] = f"Chapter {sections.index(section) + 1}"
            section["start_time"] = str(section["timestamp"])
            section_length_words = len(section["content"].split())
            print("Section length: ", section_length_words)

        return sections


    def get_chapter_summary(self, section, model='gpt-4o-mini'):

        client = OpenAI(api_key=self.api_key)
        self.logger.info(f"Getting summary for section: {section['topic']}")

        response = client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'system', 
                'content': 
                    'Summarize the following section of the video. \
                        Use the provided content to generate a summary of the section. \
                        Stay in the original language. \
                        Create Bullet Points, but dont shorten the idea of the content. Explain the topic briefly and not that they talk about it in the video. \
                        If they talk about the 5 things or the 9 types or something like that, list them. \
                        Answer the question thats given in the topic or chapter title if available. \
                        Put the topic with timestamp (in h, min, sec) [if available] in the format "hh:mm:ss" or "mm:ss" as a heading in the format: "Heading Topic (00:34)"\
                        Every Heading should be a markdown ## heading. If there is no heading title (eg. just Chapter 1), create a heading out of the content provided. \
                        Try to keep it as short as possible, but as long as necessary. '},

                {'role': 'user', 'content': str(section)}
            ],
            temperature=0.08,
            max_tokens=1024,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
            stream=True
        )

        result = ""
        for chunk in response:
            if chunk.choices[0].delta.content is not None:
                result += chunk.choices[0].delta.content

        return result
    

    def get_minimal_chapter_summary(self, section, model='gpt-4o-mini'):

        client = OpenAI(api_key=self.api_key)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'system', 
                'content': 
                    'Summarize the following chapter of a podcast as short as possible in max. 1-2 bullet points.\
                        Stay in the original language. Keep the heading.'},

                {'role': 'user', 'content': str(section)}
            ],
            temperature=0.08,
            max_tokens=256,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
        )

        result = response.choices[0].message.content
        return result


    def get_unified_summary(self, sections):
        client = OpenAI(api_key=self.api_key)

        response = client.chat.completions.create(

            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 
                'content': 
                    'Summarize the following outline of a podcast. \
                        Do not only list the topics they talk about, but briefly explain every idea you mention in the summary. \
                        Still try to keep it as short as possible. Use bullet points if possible.'},

                {'role': 'user', 'content': str(sections)}
            ],
            temperature=0.08,
            max_tokens=512,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
        )
        
        result = response.choices[0].message.content
        return result
    

    def get_whole_transcript_summary(self, transcript):
        client = OpenAI(api_key=self.api_key)

        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 
                'content': 
                    'Summarize the following transcript of a podcast. \
                        Do not only list the topics they talk about, but briefly explain every idea you mention in the summary. \
                        Still try to keep it as short as possible. Use bullet points if possible.'},

                {'role': 'user', 'content': transcript}
            ],
            temperature=0.08,
            max_tokens=1024,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
        )

        result = response.choices[0].message.content
        return result


    
def get_video(url):
    video = YouTubeVideo(url)
    video.get_data()
    return video


def example_summary(url: str, api_key=os.getenv('OPENAI_API_KEY')):
    obj = YouTubeTranscribeSummarize(url=url, api_key=api_key)
    obj.get_data()

    desc = obj.description
    outline = obj.get_outline(desc)

    if obj.transcript is None:
        ErrorMessage = f"Could not retrieve a transcript for the video {url}! \
        This is most likely caused by: \
        \n\nSubtitles are disabled for this video. \
        \n\nOpen the transcript in YouTube manually and try again. \
        This may resolve the issue."
        print(ErrorMessage)
        return ErrorMessage
    
    if obj.duration < timedelta(minutes=20):
        unified_transcript = " ".join([item["text"] for item in obj.transcript])

        summary = obj.get_whole_transcript_summary(unified_transcript)
        chap_summaries = [summary]
    else:
        pass 

    sections = []

    if outline is None:
        transcript = obj.transcript
        transcript_length = len(transcript)
        print(f"Transcript length: {transcript_length} segments")
        # outline = obj._convert_timestamps(transcript) # only if outline is found in description
        print(outline)
        sections = obj.link_transcript_without_outline(transcript)
        outline = "Synthetic"


    if outline is None:
        pass
        # check how long the transcript is and create sections if too long

    # TODO: make a summary of a short video with no outline

    # TODO: make a summary of a long video with no outline (sections)


    if outline:
        if outline != "Synthetic":
            outline = obj._convert_timestamps(outline)
            sections = obj.link_content_to_outline(content=obj.transcript, outline=outline)
        chap_summaries = []

        for section in sections:
            chap_summary = obj.get_chapter_summary(section)
            chap_summaries.append(chap_summary)

    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    long_summary_filename = f"{obj.channel}_Summary_{current_time}.md"
    short_summary_filename = f"{obj.channel}_Short_Summary_{current_time}.md"
    unified_summary_filename = f"{obj.channel}_Unified_Summary_{current_time}.md"

    short_chapters = []
    for chapter in chap_summaries:
        short_chapter = obj.get_minimal_chapter_summary(chapter)
        short_chapters.append(short_chapter)

    # Concatenate all short chapters into one string
    concatenated_short_chapters = "\n\n".join(short_chapters)
    with open(short_summary_filename, "w", encoding='utf-8') as file:
        file.write(concatenated_short_chapters)

    # Get a unified summary of all chapters
    unified_summary = obj.get_unified_summary(concatenated_short_chapters)
    with open(unified_summary_filename, "w", encoding='utf-8') as file:
        file.write(unified_summary)

    # Write the summary into a markdown file
    print("Writing summary to file ...")
    with open(long_summary_filename, "w", encoding='utf-8') as file:
        for summary in chap_summaries:
            file.write(summary + "\n\n")
    print(f"Summary successfully written to {long_summary_filename}")

    return chap_summaries


def summary_by_chapters(url: str, api_key=os.getenv('OPENAI_API_KEY')) -> list | str:
    """

    """
    obj = YouTubeTranscribeSummarize(url=url, api_key=api_key)
    obj.get_data()
    outline = obj.get_outline(obj.description)
    
    if obj.transcript is None:
        ErrorMessage = f"Could not retrieve a transcript for the video {url}! \
        This is most likely caused by: \
        \n\nSubtitles are disabled for this video. \
        \n\nOpen the transcript in YouTube manually and try again. \
        This may resolve the issue."
        print(ErrorMessage)
        return ErrorMessage
    
    outline = obj._convert_timestamps(outline)
    sections = obj.link_content_to_outline(content=obj.transcript, outline=outline)
    chap_summaries = []

    for section in sections:
        chap_summary = obj.get_chapter_summary(section)
        chap_summaries.append(chap_summary)

    return chap_summaries


def summary_entire_video(url: str, api_key=os.getenv('OPENAI_API_KEY')) -> str:
    obj = YouTubeTranscribeSummarize(url=url, api_key=api_key)
    obj.get_data()

    unified_transcript = " ".join([item["text"] for item in obj.transcript])
    summary = obj.get_whole_transcript_summary(unified_transcript)

    return summary


if __name__ == '__main__':

    url = input("\n\nPlease enter the YouTube video URL: ")
    summary_by_chapters(url=url)






