"""EXPERIMENTAL local Whisper transcription fallback for Tube-TLDR.

When a YouTube video has no captions (subtitles disabled, or the transcript
fetch failed), every summarize path in Tube-TLDR fails with "No transcript
available". This module adds an *optional* fallback: download the best audio
track with ``yt-dlp`` and transcribe it locally with ``faster-whisper``,
producing transcript entries in the **exact same dict shape** as the
``youtube-transcript-api`` path in :mod:`src.youtube_video`. Downstream code
(summaries, chapters, shorts, vault export) therefore works unchanged.

Trigger semantics (``mode``):

- ``off``   — never transcribe locally. If captions are missing, the caller
  fails exactly as before.
- ``auto``  — use captions when present; fall back to Whisper only when the
  video has no transcript.
- ``force`` — always transcribe locally, even when captions exist (useful for
  testing the fallback, or when captions are known to be low quality).

The optional dependencies (``faster-whisper``, ``yt-dlp``) are imported lazily
*inside* the functions, so this module imports cleanly when they are missing.
Use :func:`is_available` to check before relying on the fallback.

Notes / honest caveats:

- ``faster-whisper`` decodes audio containers directly via PyAV — **no ffmpeg
  binary is required**. We therefore download bestaudio *without* yt-dlp's
  ``-x`` (extract-audio) flag.
- The Whisper model is constructed on every call. For a nightly job that is
  fine; a long-lived server would want to cache it.
- ``timeout_s`` is a best-effort deadline checked *between* segments. A single
  in-flight decode/transcribe step cannot be preempted, so a partial transcript
  may be returned with a warning when the budget is exceeded.
- ``yt-dlp`` does **not** pick up the ``config.yml`` proxy settings in this
  implementation — the proxy is currently only applied to the
  YouTube-transcript/metadata path. This is a known gap (see README).
"""
from __future__ import annotations

import logging
import os
import shutil
import tempfile
import time
from datetime import timedelta
from typing import Any, Optional

_LOG_NAME = "tube-tldr-whisper"
_INSTALL_HINT = "pip install -r requirements-whisper.txt"
_VALID_MODES = ("auto", "off", "force")


class MissingDependencyError(Exception):
    """Raised when the optional Whisper/yt-dlp dependencies are not installed.

    The message always contains the install command so callers can surface it
    verbatim to the user.
    """


def _default_logger() -> logging.Logger:
    """Return the module logger, bound to stderr (never stdout)."""
    log = logging.getLogger(_LOG_NAME)
    if not log.handlers:
        handler = logging.StreamHandler()  # defaults to sys.stderr
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False
    return log


def is_available() -> bool:
    """True when both optional dependencies (faster-whisper, yt-dlp) import."""
    try:
        import faster_whisper  # noqa: F401
        import yt_dlp  # noqa: F401
    except Exception:
        return False
    return True


def get_transcription_settings(cfg: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Read the ``transcription:`` section from a loaded config dict.

    Returns a dict with ``fallback`` (one of ``auto``/``off``/``force``) and
    ``model`` (faster-whisper model size). Unknown values fall back to the
    defaults ``auto`` / ``small``. ``src.config_loader`` is intentionally not
    touched — callers pass the same ``load_config()`` result they already have.
    """
    section = (cfg or {}).get("transcription") or {}
    fallback = str(section.get("fallback") or "auto").strip().lower()
    if fallback not in _VALID_MODES:
        fallback = "auto"
    model = str(section.get("model") or "small").strip() or "small"
    return {"fallback": fallback, "model": model}


def _segment_to_entry(seg: Any) -> dict[str, Any]:
    """Convert one faster-whisper segment to the youtube-transcript-api shape.

    Mirrors :meth:`src.youtube_video.YouTubeVideo._convert_transcript_to_timedelta`
    exactly: same keys, same types (``timestamp`` is a ``timedelta`` computed
    from the segment end time).
    """
    start = float(seg.start)
    end = float(seg.end)
    duration = end - start
    end_time = start + duration
    minutes, seconds = divmod(end_time, 60)
    return {
        "start": start,
        "duration": duration,
        "text": seg.text.strip(),
        "end_time": end_time,
        "minutes": minutes,
        "seconds": seconds,
        "timestamp": timedelta(minutes=minutes, seconds=seconds),
    }


def _download_audio(url: str, tmpdir: str, logger: logging.Logger) -> str:
    """Download the best audio track for ``url`` into ``tmpdir``.

    Returns the path to the downloaded file. Raises
    :class:`MissingDependencyError` when yt-dlp is absent and ``RuntimeError``
    on any download failure.
    """
    try:
        import yt_dlp
    except ImportError as exc:  # pragma: no cover - exercised via is_available gate
        raise MissingDependencyError(
            "yt-dlp is required for the local transcription fallback. "
            f"Install it with: {_INSTALL_HINT}"
        ) from exc

    opts = {
        # bestaudio WITHOUT -x: faster-whisper decodes the container via PyAV.
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": os.path.join(tmpdir, "%(id)s.%(ext)s"),
        "quiet": True,
        "noprogress": True,
        "socket_timeout": 30,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info)
    except Exception as exc:  # noqa: BLE001 - normalise any yt-dlp failure
        raise RuntimeError(f"audio download failed: {exc}") from exc

    if not path or not os.path.exists(path):
        raise RuntimeError(f"audio download failed: no file produced for {url}")

    logger.info("Downloaded audio: %s", path)
    return path


def _run_whisper(
    audio_path: str,
    model_size: str,
    language: Optional[str],
    timeout_s: float,
    logger: logging.Logger,
) -> list[dict[str, Any]]:
    """Transcribe ``audio_path`` locally and return entries in the captions shape.

    Raises :class:`MissingDependencyError` when faster-whisper is absent and
    ``RuntimeError`` on model-load or transcription failure.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # pragma: no cover - exercised via is_available gate
        raise MissingDependencyError(
            "faster-whisper is required for the local transcription fallback. "
            f"Install it with: {_INSTALL_HINT}"
        ) from exc

    logger.info(
        "Loading whisper model '%s' (device=cpu, compute_type=int8) ...", model_size
    )
    try:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"whisper model load failed: {exc}") from exc

    logger.info(
        "Transcribing %s (language=%s, beam_size=5, vad_filter=True) ...",
        audio_path,
        language or "auto",
    )
    try:
        segments_iter, info = model.transcribe(
            audio_path,
            language=language,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            condition_on_previous_text=True,
            beam_size=5,
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"whisper transcription failed: {exc}") from exc

    started = time.monotonic()
    entries: list[dict[str, Any]] = []
    truncated = False
    for seg in segments_iter:
        entries.append(_segment_to_entry(seg))
        if timeout_s and (time.monotonic() - started) > timeout_s:
            truncated = True
            logger.warning(
                "Whisper transcription exceeded the %.0fs budget; returning a "
                "partial transcript (%d segments).",
                timeout_s,
                len(entries),
            )
            break

    if not truncated:
        logger.info(
            "Whisper transcription finished: %d segments (language=%s).",
            len(entries),
            getattr(info, "language", "?"),
        )
    return entries


def ensure_transcript(
    video: Any,
    mode: str = "auto",
    language: Optional[str] = None,
    model_size: str = "small",
    timeout_s: float = 1800,
    logger: Optional[logging.Logger] = None,
) -> bool:
    """Ensure ``video.transcript`` is populated, falling back to local Whisper.

    Args:
        video: A fetched :class:`src.youtube_video.YouTubeVideo` (needs ``url``
            and ``transcript`` attributes).
        mode: ``auto`` | ``off`` | ``force`` (see module docstring).
        language: Optional ISO language code. ``None`` lets Whisper auto-detect;
            forcing a language skips detection.
        model_size: faster-whisper model size (``tiny``/``base``/``small``/...).
        timeout_s: Best-effort transcription budget in seconds (checked between
            segments). ``<= 0`` disables the check.
        logger: Optional logger; defaults to the module logger (stderr).

    Returns:
        True when a transcript is available (already present, or produced by
        Whisper). False when ``mode == 'off'``.

    Raises:
        MissingDependencyError: optional deps not installed.
        RuntimeError: audio download or Whisper failure.
    """
    log = logger or _default_logger()
    mode = (mode or "auto").strip().lower()
    if mode not in _VALID_MODES:
        mode = "auto"

    if mode == "off":
        return False

    if getattr(video, "transcript", None):
        if mode != "force":
            return True
        log.info(
            "Whisper fallback: force mode — re-transcribing despite existing captions."
        )

    if not is_available():
        raise MissingDependencyError(
            "Local transcription fallback requires optional dependencies. "
            f"Install them with: {_INSTALL_HINT}"
        )

    url = getattr(video, "url", None)
    if not url:
        raise RuntimeError("audio download failed: video has no URL")

    tmpdir = tempfile.mkdtemp(prefix="tube-tldr-audio-")
    try:
        audio_path = _download_audio(url, tmpdir, log)
        entries = _run_whisper(audio_path, model_size, language, timeout_s, log)
        video.transcript = entries
        log.info("Transcribed locally (whisper): %d segments", len(entries))
        return True
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
