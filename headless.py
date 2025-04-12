from src.youtube_video import YouTubeVideo
from src.transcribe_summarize import summary_by_chapters
import dotenv
import os
dotenv.load_dotenv()

url = input("\n\nPlease enter the YouTube video URL: ")
video = YouTubeVideo(url=url)
video.get_data()
summary_by_chapters(video=video, api_key=os.getenv("OPENAI_API_KEY"))