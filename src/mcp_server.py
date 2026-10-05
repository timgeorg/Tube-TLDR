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
import os
import sys
from typing import Any, Optional

import dotenv

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, Tool, ToolAnnotations

# Load .env from the repo root so `python -m src.mcp_server` works standalone.
# MCP clients normally pass env explicitly; this is the fallback. Same pattern
# as headless.py.
dotenv.load_dotenv()

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

# Per-tool wall-clock budget (seconds). Video fetch + LLM summarization are
# network-bound and can stall; this is the stall guard (playbook standing rule).
# Override with the TUBE_TLDR_TOOL_TIMEOUT_S environment variable.
TOOL_TIMEOUT_S = float(os.environ.get("TUBE_TLDR_TOOL_TIMEOUT_S", "900"))

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

# All three tools are read-only w.r.t. the user's system: they fetch public
# YouTube pages/transcripts and call the configured LLM, but write no files.
_READ_ONLY_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    idempotentHint=True,
    openWorldHint=True,
)

_TOOLS = [
    Tool(
        name="summarize_by_chapters",
        title="Summarize YouTube Video by Chapters",
        description=(
            "Summarize a YouTube video chapter-by-chapter. Fetches the video, "
            "extracts chapter markers from the description, and generates a "
            "bullet-point summary for each chapter with timestamps. "
            "Best for longer videos that have chapter markers. "
            "Returns an error if the video has no chapters — use "
            "summarize_entire_video in that case."
        ),
        inputSchema=_COMMON_INPUT_SCHEMA,
        annotations=_READ_ONLY_ANNOTATIONS,
    ),
    Tool(
        name="summarize_entire_video",
        title="Summarize Entire YouTube Video",
        description=(
            "Summarize an entire YouTube video as bullet points. Fetches the "
            "video and generates a single summary covering the whole transcript. "
            "Best for shorter videos or when you want one overview regardless "
            "of chapters."
        ),
        inputSchema=_COMMON_INPUT_SCHEMA,
        annotations=_READ_ONLY_ANNOTATIONS,
    ),
    Tool(
        name="summarize_one_sentence",
        title="Summarize YouTube Video in One Sentence",
        description=(
            "Summarize a YouTube video in exactly one sentence. Fetches the "
            "video and returns a single-sentence TL;DR with the title as a "
            "heading. Best for a quick summary."
        ),
        inputSchema=_COMMON_INPUT_SCHEMA,
        annotations=_READ_ONLY_ANNOTATIONS,
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


def _error_result(message: str) -> CallToolResult:
    """Build a failure CallToolResult so MCP clients see isError=True.

    Returning a plain TextContent list would surface as a *successful* tool
    call whose text merely starts with "Error" — clients would treat it as a
    normal result. The low-level server passes CallToolResult through verbatim
    (mcp/server/lowlevel/server.py: `if isinstance(results, types.CallToolResult)`),
    so this is the supported way to signal failure.
    """
    return CallToolResult(
        content=[TextContent(type="text", text=message)],
        isError=True,
    )


# ---------------------------------------------------------------------------
# MCP handlers
# ---------------------------------------------------------------------------
@server.list_tools()
async def list_tools() -> list[Tool]:
    return _TOOLS


@server.call_tool()
async def _handle_call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
    """Handle a tool call. Registered with @server.call_tool() (which returns
    the function unchanged), so it stays directly testable as a plain coroutine.

    Failures are returned as CallToolResult(isError=True) rather than a
    success-shaped TextContent list.
    """
    url = (arguments or {}).get("url", "").strip()
    if not url:
        return _error_result("Error: 'url' is required.")

    language = (arguments or {}).get("language")
    if language:
        language = language.strip() or None

    # Fetch the video (sync I/O — run in a thread so we don't block the loop).
    try:
        video = await asyncio.wait_for(
            asyncio.to_thread(_fetch_video, url, language),
            timeout=TOOL_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.error("Timed out fetching video %s after %ss", url, TOOL_TIMEOUT_S)
        return _error_result(
            f"Error: timed out after {TOOL_TIMEOUT_S:g}s — video fetch+summarization "
            "took too long."
        )
    except Exception as e:
        logger.error("Failed to fetch video %s: %s", url, e)
        return _error_result(f"Error fetching video: {e}")

    # Summarize (sync, network-bound — also in a thread).
    try:
        if name == "summarize_by_chapters":
            coro = asyncio.to_thread(
                ts.summary_by_chapters, video=video, llm=_llm
            )
        elif name == "summarize_entire_video":
            coro = asyncio.to_thread(
                ts.summary_entire_video, video=video, llm=_llm
            )
        elif name == "summarize_one_sentence":
            coro = asyncio.to_thread(
                ts.summary_in_one_sentence, video=video, llm=_llm
            )
        else:
            return _error_result(f"Unknown tool: {name}")

        result = await asyncio.wait_for(coro, timeout=TOOL_TIMEOUT_S)
        return CallToolResult(
            content=[TextContent(type="text", text=_format_result(video, result))],
            isError=False,
        )
    except asyncio.TimeoutError:
        logger.error("Timed out summarizing %s after %ss", url, TOOL_TIMEOUT_S)
        return _error_result(
            f"Error: timed out after {TOOL_TIMEOUT_S:g}s — video fetch+summarization "
            "took too long."
        )
    except Exception as e:
        logger.error("Failed to summarize %s: %s", url, e)
        return _error_result(f"Error summarizing: {e}")


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