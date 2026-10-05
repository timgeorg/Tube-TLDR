"""Command-line interface for Tube TLDR.

Non-interactive entry point for summarizing a single YouTube video. Built for
cron jobs, shell scripts, and agent tooling: **stdout carries only the summary**
(or the JSON payload) — every progress message, warning, and error goes to
stderr.

Usage:
    python -m src.cli <url> [--style chapters|entire|one-sentence|shorts]
                           [--language de,en] [--out PATH] [--json]
                           [--config PATH] [--timeout SECONDS]

Exit codes:
    0  success
    1  configuration or I/O error (unconfigured LLM, bad proxy config, write failure)
    2  usage error (argparse) or --timeout deadline exceeded
    3  fetch failure (network error, no transcript, shorts without chapters)
    4  summarization failure (exception raised by the LLM path)

Timeout semantics (honest best-effort):
    ``--timeout`` is an overall wall-clock deadline, checked *before* each major
    stage (fetch, summarize). It is not a hard interrupt: the chapter loop lives
    inside ``src.transcribe_summarize.summary_by_chapters`` (which parallelizes
    internally), so an in-flight LLM call cannot be preempted. Individual HTTP
    calls still rely on requests' own 30s timeout and the LLM client's behavior.
    A deadline hit before a stage aborts with exit code 2 and starts no new LLM
    calls.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

from src.config_loader import get_llm_settings, get_proxy_settings, load_config
from src.youtube_video import YouTubeVideo
import src.gpt_functions as gpt
import src.transcribe_summarize as ts
# Experimental shorts machinery lives in its own package (see src/shorts).
# Imported as a module so tests can patch src.cli.shorts.create_shorts_by_chapters.
import src.shorts as shorts

_LOG_NAME = "tube-tldr-cli"
_STYLES = ("chapters", "entire", "one-sentence", "shorts")


class _ConfigError(Exception):
    """Raised for configuration problems that map to exit code 1."""


# ---------------------------------------------------------------------------
# Logging — stderr only. stdout is reserved for the summary / JSON payload.
# ---------------------------------------------------------------------------
def _setup_logging() -> logging.Logger:
    log = logging.getLogger(_LOG_NAME)
    log.setLevel(logging.INFO)
    # Rebind to the *current* sys.stderr on every call: a handler captured at
    # import time would keep writing to a stale stream (matters for tests and
    # for any caller that swaps sys.stderr).
    for handler in list(log.handlers):
        log.removeHandler(handler)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    log.addHandler(handler)
    # Never let records bubble up to a root handler that might target stdout.
    log.propagate = False
    return log


def _fail(message: str, code: int) -> int:
    """Print a human error to stderr and return the exit code."""
    print(f"Error: {message}", file=sys.stderr)
    return code


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
def _parse_args(argv: Optional[list[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m src.cli",
        description="Summarize a YouTube video from the command line (non-interactive).",
    )
    parser.add_argument(
        "url",
        help="YouTube video URL (watch, youtu.be, shorts, or embed form).",
    )
    parser.add_argument(
        "--style",
        choices=list(_STYLES),
        default="entire",
        help="Summary style (default: entire).",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="Comma-separated transcript language preference, e.g. 'de,en'.",
    )
    parser.add_argument(
        "--out",
        default=None,
        metavar="PATH",
        help="Write the summary to this file (markdown) instead of stdout.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON object instead of human-readable text.",
    )
    parser.add_argument(
        "--config",
        default=None,
        metavar="PATH",
        help="Path to a config.yml override (sets CONFIG_PATH before loading).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=900.0,
        metavar="SECONDS",
        help="Overall wall-clock deadline in seconds (default: 900; <=0 disables).",
    )
    return parser.parse_args(argv)


def _split_languages(value: Optional[str]) -> Optional[list[str]]:
    """Turn 'de,en' into ['de', 'en']; None/empty -> None (extractor default)."""
    if not value:
        return None
    langs = [part.strip() for part in value.split(",") if part.strip()]
    return langs or None


def _deadline_exceeded(deadline: Optional[float]) -> bool:
    return deadline is not None and time.monotonic() > deadline


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def _render_body(result: Any, style: str) -> str:
    """Render the summary body (no header) for the given style."""
    if style == "shorts" and isinstance(result, list):
        blocks = []
        for i, item in enumerate(result, 1):
            if isinstance(item, dict):
                heading = item.get("heading") or f"Chapter {i}"
                script = item.get("script") or ""
            else:
                heading, script = f"Chapter {i}", str(item)
            blocks.append(f"{i}. **{heading}**\n\n{script}")
        return "\n\n".join(blocks)
    if isinstance(result, list):
        return "\n\n".join(str(r) for r in result)
    return str(result)


def format_result(video: YouTubeVideo, result: Any, style: str) -> str:
    """Render the human-readable markdown summary (header + body)."""
    today = date.today().isoformat()
    header = (
        f"## {video.title}\n"
        f"*by {video.channel}*\n\n"
        f"**Uploaded:** {video.upload_date}  \n"
        f"**Link:** {video.url}  \n"
        f"**Summary created:** {today}\n\n"
    )
    return header + _render_body(result, style)


def _duration_seconds(video: YouTubeVideo) -> Optional[float]:
    duration = getattr(video, "duration", None)
    if isinstance(duration, timedelta):
        return duration.total_seconds()
    return None


def _build_json(video: YouTubeVideo, result: Any, style: str) -> dict[str, Any]:
    """Build the machine-readable payload for --json."""
    payload: dict[str, Any] = {
        "url": getattr(video, "url", None),
        "title": getattr(video, "title", None),
        "channel": getattr(video, "channel", None),
        "uploaded": getattr(video, "upload_date", None),
        "duration_seconds": _duration_seconds(video),
        "style": style,
    }
    if isinstance(result, list):
        items: list[Any] = []
        for item in result:
            if isinstance(item, dict):
                items.append(
                    {"heading": item.get("heading"), "script": item.get("script")}
                )
            else:
                items.append(str(item))
        payload["summary_items"] = items
    else:
        payload["summary_text"] = str(result)
    payload["chars"] = len(_render_body(result, style))
    return payload


def _write_out(path_str: str, text: str, log: logging.Logger) -> None:
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        log.info("Overwriting existing %s", path)
    path.write_text(text, encoding="utf-8")
    log.info("Wrote %s (%d bytes)", path, len(text.encode("utf-8")))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)

    # --config must land in the environment *before* load_config() resolves the
    # path: src.config_loader._default_config_path() reads CONFIG_PATH at call
    # time, so setting it here is sufficient (verified in tests/test_cli.py).
    if args.config:
        os.environ["CONFIG_PATH"] = str(args.config)

    log = _setup_logging()
    deadline = (
        time.monotonic() + args.timeout if args.timeout and args.timeout > 0 else None
    )

    # --- configuration -----------------------------------------------------
    try:
        cfg = load_config()
        proxy_settings = get_proxy_settings(cfg)
        if proxy_settings.enabled and proxy_settings.proxies is None:
            raise _ConfigError(
                "Proxy is enabled in config.yml, but no proxy URLs are configured."
            )
        llm_settings = get_llm_settings(cfg)
        if not llm_settings.is_configured:
            raise _ConfigError(
                "LLM is not configured. Set OLLAMA_API_KEY for Ollama Cloud, or "
                "point llm.base_url at a local server (e.g. http://localhost:11434)."
            )
        gpt.set_llm_settings(llm_settings)
    except _ConfigError as exc:
        return _fail(str(exc), 1)

    languages = _split_languages(args.language)

    # --- fetch -------------------------------------------------------------
    if _deadline_exceeded(deadline):
        return _fail("Timeout deadline exceeded before fetching the video.", 2)

    log.info("Fetching video: %s", args.url)
    try:
        video = YouTubeVideo(url=args.url, proxy=proxy_settings.proxies)
        video.get_data(languages=languages)
    except Exception as exc:  # noqa: BLE001 - surface any fetch failure as exit 3
        return _fail(f"Failed to fetch video: {exc}", 3)

    if not getattr(video, "transcript", None):
        return _fail(
            "No transcript available for this video "
            "(subtitles disabled or the transcript fetch failed).",
            3,
        )

    if args.style == "shorts" and not getattr(video, "chapters_available", False):
        return _fail(
            "This video has no chapter markers; shorts require chapters.", 3
        )

    # --- summarize ---------------------------------------------------------
    if _deadline_exceeded(deadline):
        return _fail("Timeout deadline exceeded before summarizing.", 2)

    try:
        if args.style == "chapters":
            log.info("Summarizing by chapters ...")
            result: Any = ts.summary_by_chapters(video=video, llm=llm_settings)
        elif args.style == "shorts":
            log.info("Generating shorts ideas ...")
            result = shorts.create_shorts_by_chapters(video=video, llm=llm_settings)
        elif args.style == "one-sentence":
            log.info("Summarizing (one sentence) ...")
            result = ts.summary_in_one_sentence(video=video, llm=llm_settings)
        else:
            log.info("Summarizing entire video ...")
            result = ts.summary_entire_video(video=video, llm=llm_settings)
    except Exception as exc:  # noqa: BLE001 - surface any LLM failure as exit 4
        return _fail(f"Summarization failed: {exc}", 4)

    # --- output ------------------------------------------------------------
    if args.json:
        text = json.dumps(_build_json(video, result, args.style), ensure_ascii=False, indent=2)
    else:
        text = format_result(video, result, args.style)

    if args.out:
        try:
            _write_out(args.out, text, log)
        except OSError as exc:
            return _fail(f"Failed to write {args.out}: {exc}", 1)
    else:
        print(text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
