"""
This module provides the YouTubeVideo class for extracting metadata, description, chapters, and transcript from a YouTube video.
Classes:
    YouTubeVideo: A class to represent a YouTube video and extract its metadata, description, chapters, and transcript.
"""
# Native Libraries
import re
from datetime import timedelta
# External Libraries
import requests
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi
# User-defined Imports
from src.logger import Logger


class YouTubeVideo(Logger):
    def __init__(self, url):
        self.url = url
        self.logger = self.create_logger(name=self.__class__.__name__) 
        self.logger.info(f"Creating YouTubeVideo object for URL: {url}")
    
    def get_data(self):
        self.soup = self._get_metadata()
        self.title = self._get_title()
        self.channel = self._get_channel()
        self.duration = self._get_duration()
        self.description = self._get_description()
        self.chapters_available: bool = self._check_for_timestamps()
        self.transcript = self._get_transcript()
        self.chapters = self._extract_chapters()
        self.logger.info(f"Data successfully retrieved for Video")

    
    def _get_metadata(self) -> BeautifulSoup:
        """
        Fetches and parses the metadata from the given URL.
        This method sends a GET request to the specified URL, retrieves the HTML content,
        and parses it using BeautifulSoup to extract metadata.
        Args:
            url (str): The URL from which to fetch the metadata.
        Returns:
            BeautifulSoup: A BeautifulSoup object containing the parsed HTML content.
        Raises:
            requests.exceptions.HTTPError: If the HTTP request returned an unsuccessful status code.
        """
        self.logger.info(f"Getting metadata from {self.url}")
        response = requests.get(self.url)
        response.raise_for_status()
        html = response.content
        soup = BeautifulSoup(html, features="html.parser")
        self.logger.info(f"Successfully retrieved metadata from {self.url}")
        return soup


    def _get_title(self):
        """
        Retrieves the title of a YouTube video.
        Args:
            url (str): The URL of the YouTube video.
        Returns:
            str: The title of the YouTube video if successful.
            None: If an error occurs during the retrieval process.
        """
        self.logger.info(f"Getting title ...")
        title_tag = self.soup.find("meta", property="og:title")
        title = title_tag["content"] if title_tag else "Title not found"
        self.logger.info(f"Title: {title}")
        return title
    

    def _get_channel(self):
        """
        Extracts the channel name from the provided BeautifulSoup object.
        Args:
            soup (BeautifulSoup): A BeautifulSoup object containing the parsed HTML of a YouTube page.
        Returns:
            str: The name of the channel if found, otherwise "Channel name not found".
        """
        self.logger.info(f"Getting channel ...")
        channel_tag = self.soup.find("link", itemprop="name")
        channel_name = channel_tag["content"] if channel_tag else "Channel name not found"
        self.logger.info(f"Channel: {channel_name}")
        return channel_name
    

    def _get_duration(self):
        """
        Extracts the duration of a YouTube video from the provided BeautifulSoup object.
        Args:
            soup (BeautifulSoup): A BeautifulSoup object containing the parsed HTML of a YouTube page.
        Returns:
            str: The duration of the video if found, otherwise "Duration not found".
        """
        self.logger.info(f"Getting duration ...")
        duration_tag = self.soup.find("meta", itemprop="duration")
        duration = duration_tag["content"] if duration_tag else "Duration not found"
        # Convert the ISO 8601 duration to timedelta object
        try:
            duration = re.search(r"PT(\d+H)?(\d+M)?(\d+S)?", duration).groups()
            duration = timedelta(
                hours=int(duration[0][:-1]) if duration[0] else 0,
                minutes=int(duration[1][:-1]) if duration[1] else 0,
                seconds=int(duration[2][:-1]) if duration[2] else 0
            )
            self.logger.info(f"Duration: {duration}")

        except Exception as e:
            self.logger.error(f"An error occurred while parsing the duration: {e}")
            duration = "Duration not found"
        
        return duration
    

    def _get_description(self):
        """
        Extracts the description from a YouTube video page.
        Args:
            url (str): The URL of the YouTube video.
        Returns:
            str: The description of the YouTube video.
        """
        try:
            # Attempt to extract the description using regex
            description_regex = re.compile(r'(?<=shortDescription":").*?(?=","isCrawlable)')
            description = description_regex.search(str(self.soup))
            if description:
                return description.group(0).replace('\\n', '\n')
        except Exception as e:
            self.logger.error(f"Error extracting description using regex: {e}")

        # Attempt to extract the description from a <meta> tag
        description_meta = self.soup.find('meta', attrs={'name': 'description'})
        if description_meta:
            return description_meta.get('content', '').strip()

        # Attempt to extract the description from a <p> tag
        description_tag = self.soup.find('p', class_='content')  # Adjust class if needed
        if description_tag:
            return description_tag.get_text(strip=True)

        # Log and raise an exception if description is not found
        self.logger.error("Description not found in the page.")
        raise Exception("Description not found.")


    def _check_for_timestamps(self) -> bool:
        """
        Checks if the description contains "0:00" or "00:00".
        Returns:
            bool: True if "0:00" or "00:00" is found in the description, False otherwise.
        """
        self.logger.info(f"Checking for timestamps in description ...")
        if "0:00" in self.description or "00:00" in self.description:
            self.logger.info(f"Timestamps found in description.")
            return True
        else:
            self.logger.info(f"No timestamps found in description.")
            return False
        
        
    def _convert_transcript_to_timedelta(self, data: list[dict]) -> list[dict]:
        """
        Converts transcript data to include end time, minutes, seconds, and timestamp.
        Args:
            data (list of dict): A list of dictionaries where each dictionary represents a transcript item 
                with 'start' and 'duration' keys.
        Returns:
            list of dict: The modified list of dictionaries with additional keys:
                - 'end_time': The end time of the transcript item.
                - 'minutes': The minute part of the end time.
                - 'seconds': The second part of the end time.
                - 'timestamp': A timedelta object representing the end time.
        """
        for item in data:
            item["end_time"] = item['start'] + item['duration']
            end_time = float(item['start']) + float(item['duration'])
            minutes, seconds = divmod(end_time, 60)
            item["minutes"] = minutes
            item["seconds"] = seconds
            item["timestamp"] = timedelta(minutes=item["minutes"], seconds=item["seconds"])

        return data
        
    
    def _extract_chapters(self):
        """
        If available, extract the chapters from the description of a YouTube video.
        Args:
            description (str): The description of the YouTube video.
        Returns:
            list: A list of dictionaries containing the chapters with 'timestamp' and 'content' keys.
        """
        if not self.chapters_available:
            return None
        
        self.logger.info(f"Extracting chapters ...")
        chapters = []

        timestamp_regex = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")
        """
        Explanation:
        1. b: This is a word boundary anchor. It asserts a position at the start or end of a word. 
            This ensures that the timestamp is not part of a larger word.
        2. \d{1,2}: This matches one or two digits. It represents the hours part of the timestamp, allowing for values from 0 to 99.
        3. :: This matches the colon character : which separates hours from minutes.
        4. \d{2}: This matches exactly two digits. It represents the minutes part of the timestamp, allowing for values from 00 to 59.
        5. (?::\d{2})?: This is a non-capturing group (?: ... ) that matches the colon : followed by exactly two digits \d{2}. 
            The ? at the end makes this group optional, meaning it can match zero or one time. 
            This part represents the optional seconds part of the timestamp, allowing for values from 00 to 59.
        6. b: Another word boundary anchor to ensure the timestamp is not part of a larger word.
        """
        timestamps = timestamp_regex.findall(self.description)
        chapter_titles = re.split(timestamp_regex, self.description)[1:]

        for timestamp, title in zip(timestamps, chapter_titles):
            chapters.append({"timestamp": timestamp, "content": title.strip()})
        return chapters
    

    def _get_transcript(self):
        """
        Retrieves the transcript of a YouTube video and converts it to a timestamped format.
        Args:
            url (str): The URL of the YouTube video.
        Returns:
            list: A list of dictionaries containing the transcript with timestamps if successful.
            None: If an error occurs during the retrieval process.
        Raises:
            Exception: If an error occurs while retrieving the transcript.
        """
        self.logger.info(f"Getting transcript ...")
        video_id = self.url.split('=')[-1]

        try:
            data = YouTubeTranscriptApi.get_transcript(video_id, languages=("en", "de"))
            timestamped_data = self._convert_transcript_to_timedelta(data)
            self.logger.info(f"Successfully retrieved transcript")
            return timestamped_data
        
        except Exception as e:
            self.logger.error(f"An error occurred while retrieving the transcript: {e}")
            return None

