"""(Experimental) Short-form script generation from chapter markers.

Moved out of the core summarizer (``src.transcribe_summarize`` /
``src.gpt_functions``) so the experimental shorts machinery is cleanly
separated from the three stable summarize tools.

Note: ``_chat`` is imported by its private name from ``src.gpt_functions`` —
this is an intentional intra-project import of a shared internal helper, not a
public API. ``_DEFAULT_LLM`` is read through the module object (``gpt._DEFAULT_LLM``)
rather than imported by value, because ``set_llm_settings()`` rebinds it at
runtime and a by-value import would capture a stale object.
"""
from __future__ import annotations

from typing import Optional

import src.gpt_functions as gpt
from src.gpt_functions import _chat
from src.config_loader import LLMSettings
from src.youtube_video import YouTubeVideo
from src.transcribe_summarize import YouTubeTranscribeSummarize


def rework_transcript_to_sentences(transcript_item: dict, llm: Optional[LLMSettings] = None) -> dict:
    """
    """
    return _chat(
        messages=[
            {'role': 'system',
            'content':
                'Rework the following transcript item to a more readable format.\
                Stay in the original language!  \
                Do not change the content, just make it more readable. \
                Shorten this into whole sentences. I want you to build whole sentences with the timestamps, but keep it as short as it makes sense to get a whole and finished sentence. \
                You are allowed to polish that sentence and add punctuation, etc.'},

            {'role': 'user', 'content': str(transcript_item)}
        ],
        temperature=0.1,
        max_tokens=512,
        llm=llm,
    )


def create_shorts_script(cleaned_transcript: str, llm: Optional[LLMSettings] = None):
    """
    """
    s = llm or gpt._DEFAULT_LLM
    return _chat(
        messages=[
            {'role': 'system',
            'content':
                'Create a Voiceover for short-form content based on the provided trancript. \
                Stay in the original language and keep it short, engaging and conversational! \
                Create a HOOK at the beginning of the video like "Hast du dich schon mal gefragt, ...?" \
                and a CALL TO ACTION at the end of the video, e.g to check out the full video on the channel. \
                Make it as short as possible! No AI slop or unnecessary words. Absolutely laidback and on point. \
                Create a smooth text without timestamps or block elements to that it can immediately be sythezized to Voice. \
                '},

            {'role': 'user', 'content': cleaned_transcript}
        ],
        model=s.model_heavy,
        temperature=0.1,
        max_tokens=512,
        llm=llm,
    )


def create_shorts_by_chapters(video: YouTubeVideo, llm: Optional[LLMSettings] = None) -> list[str]:
    """(Experimental) Generate a short-form script for each chapter of a video.

    Requires chapter markers; raises ``ValueError`` for videos without them.
    """
    if not getattr(video, "transcript", None) or not getattr(video, "chapters_available", False):
        raise ValueError(
            "Video has no chapter markers; shorts require chapters. "
            "Use summarize_entire_video instead."
        )
    obj = YouTubeTranscribeSummarize(youtube_video=video)
    outline = obj.convert_timestamps_to_timedelta(obj.youtube_video.chapters)
    sections = obj.link_content_to_outline(content=obj.youtube_video.transcript, outline=outline, short_form=True)
    shorts_per_chapter = []
    for section in sections:
        chapter_script = rework_transcript_to_sentences(section, llm=llm)
        shorts_script = create_shorts_script(chapter_script, llm=llm)
        shorts_per_chapter.append(
            {
                "heading": section["heading"],
                "script": shorts_script,
            }
        )
    return shorts_per_chapter
