"""
MCP server exposing YouTube video summarization tools.

Any MCP-compatible agent (GitHub Copilot, opencode, Claude Desktop, Cursor)
can call these tools to summarize YouTube videos. Each tool fetches the video
internally — callers only need to provide a URL.

Run:
    python -m src.mcp_server

The server uses stdio transport (no HTTP server needed). LLM provider/model
and proxy settings come from config.yml + environment variables, exactly like
the Streamlit UI.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ---------------------------------------------------------------------------
# Logging — must be on stderr, NEVER stdout (stdout is the MCP transport).
# Configure before importing modules that create loggers.
# ---------------------------------------------------------------------------
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
# Force any pre-existing handlers to stderr too.
for name in ("YouTubeVideo", "YouTubeTranscribeSummarize", "tube-tldr-mcp"):
    lg = logging.getLogger(name)
    lg.handlers = []  # clear any stdout handlers added by Logger.create_logger
    lg.addHandler(logging.StreamHandler(sys.stderr))

logger = logging.getLogger("tube-tldr-mcp")

# ---------------------------------------------------------------------------
# Import existing logic (after logging is configured).
# ---------------------------------------------------------------------------
import src.transcribe_summarize as ts
import src.gpt_functions as gpt
from src.youtube_video import YouTubeVideo
from src.config_loader import load_config, get_proxy_settings, get_llm_settings

# Load config once at startup — same source as the Streamlit UI.
_cfg = load_config()
_proxy = get_proxy_settings(_cfg)
_llm = get_llm_settings(_cfg)
gpt.set_llm_settings(_llm)

logger.info(
    "MCP server starting — provider=%s, model=%s, base_url=%s",
    _llm.provider, _llm.model, _llm.base_url,
)

server = Server("tube-tldr")

# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------
_COMMON_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "url": {
            "type": "string",
            "description": "YouTube video URL (watch, youtu.be, shorts, or embed format).",
        },
        "language": {
            "type": "string",
            "description": (
                "Preferred transcript language code (e.g. 'en', 'de'). "
                "Defaults to ['de', 'en']."
            ),
        },
    },
    "required": ["url"],
}

_TOOLS = [
    Tool(
        name="summarize_by_chapters",
        description=(
            "Summarize a YouTube video chapter-by-chapter. Fetches the video, "
            "extracts chapter markers from the description, and generates a "
            "bullet-point summary for each chapter with timestamps. "
            "Best for longer videos that have chapter markers. "
            "Returns an error if the video has no chapters — use "
            "summarize_entire_video in that case."
        ),
        inputSchema=_COMMON_INPUT_SCHEMA,
    ),
    Tool(
        name="summarize_entire_video",
        description=(
            "Summarize an entire YouTube video as bullet points. Fetches the "
            "video and generates a single summary covering the whole transcript. "
            "Best for shorter videos or when you want one overview regardless "
            "of chapters."
        ),
        inputSchema=_COMMON_INPUT_SCHEMA,
    ),
    Tool(
        name="summarize_one_sentence",
        description=(
            "Summarize a YouTube video in exactly one sentence. Fetches the "
            "video and returns a single-sentence TL;DR with the title as a "
            "heading. Best for a quick summary."
        ),
        inputSchema=_COMMON_INPUT_SCHEMA,
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _fetch_video(url: str, language: Optional[str]) -> YouTubeVideo:
    """Create a YouTubeVideo, fetch its data, and return it.

    Raises on fetch failure or missing transcript.
    """
    languages = [language] if language else None
    video = YouTubeVideo(url=url, proxy=_proxy.proxies)
    video.get_data(languages=languages)
    if not video.transcript:
        raise ValueError(
            "No transcript available for this video. "
            "Subtitles may be disabled or the transcript fetch failed."
        )
    return video


def _format_result(video: YouTubeVideo, result: Any) -> str:
    """Prefix the result with video title/channel/date/link for agent context."""
    from datetime import date
    today = date.today().isoformat()
    header = (
        f"## {video.title}\n"
        f"*by {video.channel}*\n\n"
        f"**Uploaded:** {video.upload_date}  \n"
        f"**Link:** {video.url}  \n"
        f"**Summary created:** {today}\n\n"
    )
    if isinstance(result, list):
        return header + "\n\n".join(str(r) for r in result)
    return header + str(result)


# ---------------------------------------------------------------------------
# MCP handlers
# ---------------------------------------------------------------------------
@server.list_tools()
async def list_tools() -> list[Tool]:
    return _TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    url = (arguments or {}).get("url", "").strip()
    if not url:
        return [TextContent(type="text", text="Error: 'url' is required.")]

    language = (arguments or {}).get("language")
    if language:
        language = language.strip() or None

    # Fetch the video (sync I/O — run in a thread so we don't block the loop).
    try:
        video = await asyncio.to_thread(_fetch_video, url, language)
    except Exception as e:
        logger.error("Failed to fetch video %s: %s", url, e)
        return [TextContent(type="text", text=f"Error fetching video: {e}")]

    # Summarize (sync, network-bound — also in a thread).
    try:
        if name == "summarize_by_chapters":
            result = await asyncio.to_thread(
                ts.summary_by_chapters, video=video, llm=_llm
            )
        elif name == "summarize_entire_video":
            result = await asyncio.to_thread(
                ts.summary_entire_video, video=video, llm=_llm
            )
        elif name == "summarize_one_sentence":
            result = await asyncio.to_thread(
                ts.summary_in_one_sentence, video=video, llm=_llm
            )
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        return [TextContent(type="text", text=_format_result(video, result))]
    except Exception as e:
        logger.error("Failed to summarize %s: %s", url, e)
        return [TextContent(type="text", text=f"Error summarizing: {e}")]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())