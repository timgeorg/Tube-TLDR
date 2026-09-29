# Native Libraries
import json
import os
from datetime import datetime, timedelta
from typing import Optional
# External Libraries
from openai import OpenAI # OR: from openai import AzureOpenAI
# User-defined Libraries
try:
    import src.gpt_functions as gpt
    from src.youtube_video import YouTubeVideo
    from src.logger import Logger
    from src.config_loader import LLMSettings
except ImportError:
    from youtube_video import YouTubeVideo
    from logger import Logger
    import gpt_functions as gpt
    from config_loader import LLMSettings
from concurrent.futures import ThreadPoolExecutor, as_completed


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
                        if "transcript" not in item and short_form == True:
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


def _require_transcript(video: YouTubeVideo) -> None:
    """Raise a clear error if the video has no transcript.

    The transcript can be None when subtitles are disabled or the fetch failed.
    Without this guard, downstream code crashes with a confusing
    "'NoneType' object is not iterable" error.
    """
    if not getattr(video, "transcript", None):
        raise ValueError(
            "No transcript available for this video. "
            "Subtitles may be disabled, or the transcript fetch failed. "
            "Try opening the transcript in YouTube manually, then reload the video."
        )


def summary_by_chapters(video: YouTubeVideo, llm: Optional[LLMSettings] = None) -> list[str]:
    """
    Summarizes the YouTube video by chapters.
    Converts chapter timestamps to timedelta objects and links the transcript content.
    Args:
        video (YouTubeVideo): The YouTube video object.
        llm (LLMSettings, optional): LLM connection settings.
    Returns:
        list[str]: A list of chapter summaries.
    """
    _require_transcript(video)
    if not getattr(video, "chapters", None):
        raise ValueError(
            "This video has no chapter markers in its description. "
            "Use 'summarize_entire_video' or 'summarize_one_sentence' instead."
        )
    obj = YouTubeTranscribeSummarize(youtube_video=video)
    outline = obj.convert_timestamps_to_timedelta(obj.youtube_video.chapters)
    sections = obj.link_content_to_outline(content=obj.youtube_video.transcript, outline=outline)

    # Parallelize chapter summaries (network-bound -> threads work well here)
    max_workers = min(8, len(sections)) or 1  # tune as needed (and to avoid rate-limits)
    chap_summaries = [None] * len(sections)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(gpt.get_chapter_summary, sections[i], llm=llm): i
            for i in range(len(sections))
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            chap_summaries[idx] = future.result()

    return chap_summaries


def create_shorts_by_chapters(video: YouTubeVideo, llm: Optional[LLMSettings] = None) -> list[str]:

    _require_transcript(video)
    obj = YouTubeTranscribeSummarize(youtube_video=video)
    outline = obj.convert_timestamps_to_timedelta(obj.youtube_video.chapters)
    sections = obj.link_content_to_outline(content=obj.youtube_video.transcript, outline=outline, short_form=True)
    shorts_per_chapter = []
    for section in sections:
        chapter_script = gpt.rework_transcript_to_sentences(section, llm=llm)
        shorts_script = gpt.create_shorts_script(chapter_script, llm=llm)
        shorts_per_chapter.append(
            {
                "heading": section["heading"],
                "script": shorts_script,
            }
        )
    return shorts_per_chapter


def summary_entire_video(video: YouTubeVideo, llm: Optional[LLMSettings] = None) -> str:
    """
    Summarizes the entire YouTube video.
    Converts the transcript into a single string and generates a summary.
    Args:
        video (YouTubeVideo): The YouTube video object.
        llm (LLMSettings, optional): LLM connection settings.
    Returns:
        str: The summary of the entire video.
    """
    _require_transcript(video)
    obj = YouTubeTranscribeSummarize(youtube_video=video)
    unified_transcript = " ".join([item["text"] for item in obj.youtube_video.transcript])
    summary = gpt.get_whole_transcript_summary(unified_transcript, title=video.title, llm=llm)
    return summary


def summary_in_one_sentence(video: YouTubeVideo, llm: Optional[LLMSettings] = None) -> str:
    """
    Generates a one-sentence summary of the entire YouTube video.
    Converts the transcript into a single string and generates a summary.
    Args:
        video (YouTubeVideo): The YouTube video object.
        llm (LLMSettings, optional): LLM connection settings.
    Returns:
        str: The one-sentence summary of the entire video.
    """
    _require_transcript(video)
    obj = YouTubeTranscribeSummarize(youtube_video=video)
    unified_transcript = " ".join([item["text"] for item in obj.youtube_video.transcript])
    summary = gpt.get_one_sentence_summary(unified_transcript, obj.youtube_video.title, llm=llm)
    return summary


if __name__ == '__main__':

    url = input("\n\nPlease enter the YouTube video URL: ")
    video = YouTubeVideo(url=url)
    video.get_data()
    summaries = summary_by_chapters(video=video)
    for s in summaries:
        print(s)
    # summary_entire_video(video=video)
    # summary_in_one_sentence(video=video)






