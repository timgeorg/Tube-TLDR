from src.youtube_video import YouTubeVideo
from src.transcribe_summarize import summary_by_chapters, create_shorts_by_chapters
from src.config_loader import load_config, get_proxy_settings
import dotenv
import os
dotenv.load_dotenv()

url = input("\n\nPlease enter the YouTube video URL: ")
cfg = load_config()
proxy_settings = get_proxy_settings(cfg)
if proxy_settings.enabled and proxy_settings.proxies is None:
	raise RuntimeError("Proxy is enabled in config.yml, but no proxy URLs are configured.")

video = YouTubeVideo(url=url, proxy=proxy_settings.proxies)
video.get_data()
ideas = create_shorts_by_chapters(video=video, api_key=os.getenv("OPENAI_API_KEY"))
print("\n\nIdeas for Shorts:")
print(ideas)