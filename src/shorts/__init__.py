"""(Experimental) Short-form video script generation.

This package is **experimental** and deliberately kept out of the core
summarizer. It turns a video's chapter markers into per-chapter short-form
(Shorts / Reels / TikTok) voiceover scripts.

Caveats:
  - Requires chapter markers. Videos without chapters raise ``ValueError``.
  - Output quality varies; the prompts are still being tuned.

For the stable product, use the three core summarize tools in
``src.transcribe_summarize`` instead.
"""
from src.shorts.generator import create_shorts_by_chapters

__all__ = ["create_shorts_by_chapters"]
