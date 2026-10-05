"""EXPERIMENTAL command-line entry point for short-form script generation.

This is a separate, experimental entry point for the shorts machinery that
lives in ``src.shorts``. It is intentionally decoupled from the core CLI
(``src.cli``): the ~20 lines of config/fetch wiring below are duplicated on
purpose so the experimental path can change (or be dropped) without touching
the stable product.

Usage:
    python -m src.shorts_cli <url> [--language de,en] [--out PATH] [--config PATH]

Exit codes:
    0  success
    1  configuration or I/O error (unconfigured LLM, bad proxy config, write failure)
    3  no transcript, or no chapter markers (shorts require chapters)

Quality disclaimer: output quality varies. Shorts are experimental and the
prompts are still being tuned.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from src.config_loader import get_llm_settings, get_proxy_settings, load_config
from src.youtube_video import YouTubeVideo
import src.gpt_functions as gpt
from src.shorts import create_shorts_by_chapters

_LOG_NAME = "tube-tldr-shorts"


class _ConfigError(Exception):
    """Raised for configuration problems that map to exit code 1."""


def _setup_logging() -> logging.Logger:
    log = logging.getLogger(_LOG_NAME)
    log.setLevel(logging.INFO)
    for handler in list(log.handlers):
        log.removeHandler(handler)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    log.addHandler(handler)
    log.propagate = False
    return log


def _fail(message: str, code: int) -> int:
    print(f"Error: {message}", file=sys.stderr)
    return code


def _parse_args(argv: Optional[list[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m src.shorts_cli",
        description="EXPERIMENTAL: generate short-form video scripts per chapter.",
    )
    parser.add_argument(
        "url",
        help="YouTube video URL (watch, youtu.be, shorts, or embed form).",
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
        help="Write the scripts to this file (markdown) instead of stdout.",
    )
    parser.add_argument(
        "--config",
        default=None,
        metavar="PATH",
        help="Path to a config.yml override (sets CONFIG_PATH before loading).",
    )
    return parser.parse_args(argv)


def _split_languages(value: Optional[str]) -> Optional[list[str]]:
    if not value:
        return None
    langs = [part.strip() for part in value.split(",") if part.strip()]
    return langs or None


def _render(result: list) -> str:
    blocks = []
    for i, item in enumerate(result, 1):
        if isinstance(item, dict):
            heading = item.get("heading") or f"Chapter {i}"
            script = item.get("script") or ""
        else:
            heading, script = f"Chapter {i}", str(item)
        blocks.append(f"{i}. **{heading}**\n\n{script}")
    return "\n\n".join(blocks)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)

    if args.config:
        os.environ["CONFIG_PATH"] = str(args.config)

    log = _setup_logging()

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

    # --- generate ----------------------------------------------------------
    log.info("Generating shorts scripts ...")
    try:
        result = create_shorts_by_chapters(video=video, llm=llm_settings)
    except ValueError as exc:
        # No transcript / no chapter markers -> exit 3.
        return _fail(str(exc), 3)
    except Exception as exc:  # noqa: BLE001 - surface any LLM failure as exit 1
        return _fail(f"Shorts generation failed: {exc}", 1)

    # --- output ------------------------------------------------------------
    text = _render(result)
    if args.out:
        try:
            path = Path(args.out)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            log.info("Wrote %s (%d bytes)", path, len(text.encode("utf-8")))
        except OSError as exc:
            return _fail(f"Failed to write {args.out}: {exc}", 1)
    else:
        print(text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
