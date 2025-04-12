# Native Libraries
import json
import os
from datetime import datetime, timedelta
# External Libraries
from openai import OpenAI # OR: from openai import AzureOpenAI
# User-defined Libraries
try:
    import src.gpt_functions as gpt
    from src.youtube_video import YouTubeVideo
    from src.logger import Logger
except ImportError:
    from youtube_video import YouTubeVideo
    from logger import Logger
    import gpt_functions as gpt


class YouTubeTranscribeSummarize(Logger):
    def __init__(self, youtube_video: YouTubeVideo):
        self.youtube_video = youtube_video
        self.logger = self.create_logger(name=self.__class__.__name__)
        self.logger.info(f"Creating YouTubeTranscribeSummarize object for video: {self.youtube_video.url}")

    def convert_timestamps_to_timedelta(self, chapters: dict) -> list[dict]:
        """
        Converts timestamps in the given result dictionary from string format to timedelta objects.
        Args:
            outlist (dict): A dictionary containing the list of timestamps to convert.
                timestamp (str): The timestamp string to convert.
                text (str): The text associated with the timestamp.
            Example:
                chapters = [
                    {"timestamp": "00:00:01", "text": "Hello World"},
                    {"timestamp": "00:02:34", "text": "Goodbye World"}
                ]
        Returns:
            list: A list of dictionaries with the timestamps converted to timedelta objects.
        Raises:
            ValueError: If a timestamp is in an unexpected format.
        """
        for item in chapters:
            item["timestr"] = item["timestamp"]
            time_parts = item["timestamp"].split(":")
            if len(time_parts) == 2:  # Format is "MM:SS"
                minutes, seconds = map(int, time_parts)
                item["timestamp"] = timedelta(minutes=minutes, seconds=seconds)
            elif len(time_parts) == 3:  # Format is "HH:MM:SS"
                hours, minutes, seconds = map(int, time_parts)
                item["timestamp"] = timedelta(hours=hours, minutes=minutes, seconds=seconds)
            else:
                raise ValueError(f"Unexpected timestamp format: {item['timestamp']}")
        return chapters


    def link_content_to_outline(self, content: list, outline: list, short_form: bool = False) -> list[dict]:
        """
        Group the transcript content into sections based on the video outline
        Args:
            content (list): List of dictionaries containing the transcript content
            outline (list): List of dictionaries containing the video outline (chapters)
                keys: 'timestr' (str), 'timestamp' (timedelta), content (str)
            short_form (bool): Flag to indicate if the transcript shall be cleaned for short form content creation. Defaults to False.
        Returns:
            list: List of dictionaries containing the video outline with the content linked to each section
                keys: 'timestr' (str), 'timestamp (timedelta), 'heading' (str), 'content' (str)
        """
        for item in outline:
            item["heading"] = item["content"]
            item["content"] = []
            start_time = item["timestamp"]
            end_time = outline[outline.index(item) + 1]["timestamp"] if outline.index(item) + 1 < len(outline) else None
            
            for entry in content:
                if end_time:
                    if start_time <= entry["timestamp"] < end_time:
                        item["content"].append(entry["text"])
                        # Transcript for short form content creation
                        if "transcript" not in item and short_form = True:
                            item["transcript"] = []
                        item["transcript"].append({
                            "text": entry["text"],
                            "timestamp": entry["timestamp"],
                            "timestr": entry["start"]
                        })
                else:
                    if entry["timestamp"] >= start_time:
                        item["content"].append(entry["text"])

        # Join the content into a single string for each section
        for item in outline:
            item["content"] = " ".join(item["content"])
        return outline


    def link_transcript_without_outline(self, content):

        # TODO: Work in progress

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


def summary_by_chapters(video: YouTubeVideo, api_key: str) -> list[str]:
    """
    Summarizes the YouTube video by chapters.
    Converts chapter timestamps to timedelta objects and links the transcript content. 
    Args:
        video (YouTubeVideo): The YouTube video object.
        api_key (str): The OpenAI API key.
    Returns:
        list[str]: A list of chapter summaries.
    """
    obj = YouTubeTranscribeSummarize(youtube_video=video)
    outline = obj.convert_timestamps_to_timedelta(obj.youtube_video.chapters)
    sections = obj.link_content_to_outline(content=obj.youtube_video.transcript, outline=outline)
    

    chap_summaries = []
    for section in sections:
        chap_summary = gpt.get_chapter_summary(section, api_key=api_key)
        chap_summaries.append(chap_summary)

    return chap_summaries


def create_shorts_by_chapters(video: YouTubeVideo, api_key: str) -> list[str]:

    obj = YouTubeTranscribeSummarize(youtube_video=video)
    outline = obj.convert_timestamps_to_timedelta(obj.youtube_video.chapters)
    sections = obj.link_content_to_outline(content=obj.youtube_video.transcript, outline=outline, short_form=True)
    for section in sections:
        chapter_script = gpt.rework_transcript_to_sentences(section)
        shorts_script = gpt.create_shorts_script(chapter_script))



def summary_entire_video(video: YouTubeVideo, api_key: str) -> str:
    """
    Summarizes the entire YouTube video.
    Converts the transcript into a single string and generates a summary.
    Args:
        video (YouTubeVideo): The YouTube video object.
        api_key (str): The OpenAI API key.
    Returns:
        str: The summary of the entire video.
    """
    obj = YouTubeTranscribeSummarize(youtube_video=video)
    unified_transcript = " ".join([item["text"] for item in obj.youtube_video.transcript])
    summary = gpt.get_whole_transcript_summary(unified_transcript, api_key=api_key)
    return summary


def summary_in_one_sentence(video: YouTubeVideo, api_key: str) -> str:
    """
    Generates a one-sentence summary of the entire YouTube video.
    Converts the transcript into a single string and generates a summary.
    Args:
        video (YouTubeVideo): The YouTube video object.
        api_key (str): The OpenAI API key.
    Returns:
        str: The one-sentence summary of the entire video.
    """
    obj = YouTubeTranscribeSummarize(youtube_video=video)
    unified_transcript = " ".join([item["text"] for item in obj.youtube_video.transcript])
    summary = gpt.get_one_sentence_summary(unified_transcript, obj.youtube_video.title, api_key=api_key)
    return summary


if __name__ == '__main__':

    url = input("\n\nPlease enter the YouTube video URL: ")
    summary_by_chapters(url=url)
    # summary_entire_video(url=url)






