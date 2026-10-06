"""Tests for the optional local Whisper fallback (src/whisper_fallback.py).

Everything is mocked: no network, no yt-dlp download, no faster-whisper model
load. The optional dependencies are stubbed by injecting fake modules into
``sys.modules`` (the module imports them lazily *inside* the functions), so the
tests run on a machine where the extras are not installed.

The hard invariant under test is **shape parity**: a Whisper-produced transcript
entry must be byte-for-byte structurally identical to a captions entry produced
by ``YouTubeVideo._convert_transcript_to_timedelta`` — same keys, same types,
same ``timedelta`` timestamp. Downstream code (summaries, chapters, shorts,
vault export) relies on that.
"""
# Let Python locate the source code
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
import types
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import src.whisper_fallback as wf
from src.youtube_video import YouTubeVideo


class _FakeSegment:
    """Minimal stand-in for a faster-whisper segment (start/end/text)."""

    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text


def _fake_video(url="https://www.youtube.com/watch?v=test", transcript=None):
    video = MagicMock()
    video.url = url
    video.transcript = transcript
    return video


def _install_fake_faster_whisper(segments, language="de"):
    """Inject a stub ``faster_whisper`` module whose WhisperModel yields segments."""
    module = types.ModuleType("faster_whisper")

    class _FakeModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, *args, **kwargs):
            return iter(segments), SimpleNamespace(language=language)

    module.WhisperModel = _FakeModel
    return module


class TestGetTranscriptionSettings(unittest.TestCase):
    def test_defaults_on_empty_config(self):
        self.assertEqual(
            wf.get_transcription_settings({}),
            {"fallback": "auto", "model": "small"},
        )

    def test_defaults_on_none(self):
        self.assertEqual(
            wf.get_transcription_settings(None),
            {"fallback": "auto", "model": "small"},
        )

    def test_overrides_are_read(self):
        cfg = {"transcription": {"fallback": "force", "model": "medium"}}
        self.assertEqual(
            wf.get_transcription_settings(cfg),
            {"fallback": "force", "model": "medium"},
        )

    def test_invalid_fallback_falls_back_to_auto(self):
        cfg = {"transcription": {"fallback": "banana"}}
        self.assertEqual(wf.get_transcription_settings(cfg)["fallback"], "auto")

    def test_fallback_is_case_and_whitespace_insensitive(self):
        cfg = {"transcription": {"fallback": "  FORCE  "}}
        self.assertEqual(wf.get_transcription_settings(cfg)["fallback"], "force")

    def test_empty_model_falls_back_to_small(self):
        cfg = {"transcription": {"model": "   "}}
        self.assertEqual(wf.get_transcription_settings(cfg)["model"], "small")


class TestSegmentToEntry(unittest.TestCase):
    def test_exact_key_set_and_types(self):
        entry = wf._segment_to_entry(_FakeSegment(5.0, 9.0, "  Hello  "))

        self.assertEqual(
            set(entry.keys()),
            {"start", "duration", "text", "end_time", "minutes", "seconds", "timestamp"},
        )
        self.assertIsInstance(entry["start"], float)
        self.assertIsInstance(entry["duration"], float)
        self.assertIsInstance(entry["text"], str)
        self.assertIsInstance(entry["end_time"], float)
        self.assertIsInstance(entry["minutes"], float)
        self.assertIsInstance(entry["seconds"], float)
        self.assertIsInstance(entry["timestamp"], timedelta)

    def test_values_and_timestamp_math(self):
        entry = wf._segment_to_entry(_FakeSegment(5.0, 9.0, "  Hello  "))

        self.assertEqual(entry["start"], 5.0)
        self.assertEqual(entry["duration"], 4.0)
        self.assertEqual(entry["text"], "Hello")  # stripped
        self.assertEqual(entry["end_time"], 9.0)
        self.assertEqual(entry["minutes"], 0.0)
        self.assertEqual(entry["seconds"], 9.0)
        self.assertEqual(entry["timestamp"], timedelta(minutes=0, seconds=9))

    def test_timestamp_matches_divmod_of_end_time(self):
        entry = wf._segment_to_entry(_FakeSegment(120.0, 187.5, "x"))
        end_time = entry["end_time"]
        expected = timedelta(minutes=end_time // 60, seconds=end_time % 60)
        self.assertEqual(entry["timestamp"], expected)

    def test_structural_parity_with_captions_converter(self):
        """Whisper entry == captions entry for the same synthetic segment.

        The captions path is ``YouTubeVideo._convert_transcript_to_timedelta``,
        an instance method that only touches its ``data`` argument. We build a
        bare instance with ``__new__`` (same trick as tests/test_youtube_video.py)
        so no network/logger setup runs, then feed both converters the same
        start/duration/text and assert the resulting dicts are equal. This is a
        real comparison against the production converter, not a re-implementation.
        """
        captions_video = YouTubeVideo.__new__(YouTubeVideo)
        captions_entry = captions_video._convert_transcript_to_timedelta(
            [{"start": 5.0, "duration": 4.0, "text": "Hello"}]
        )[0]

        whisper_entry = wf._segment_to_entry(_FakeSegment(5.0, 9.0, "Hello"))

        self.assertEqual(whisper_entry, captions_entry)
        self.assertEqual(set(whisper_entry.keys()), set(captions_entry.keys()))


class TestEnsureTranscriptModes(unittest.TestCase):
    def test_mode_off_returns_false_and_touches_nothing(self):
        video = _fake_video(transcript=None)

        def _boom():
            raise AssertionError("is_available must not be called in mode=off")

        with patch.object(wf, "is_available", side_effect=_boom):
            result = wf.ensure_transcript(video, mode="off")

        self.assertFalse(result)
        self.assertIsNone(video.transcript)

    def test_mode_off_with_captions_present_keeps_them(self):
        """captions→off: ensure_transcript is a harmless no-op, captions survive."""
        existing = [{"text": "existing captions", "timestamp": timedelta(0)}]
        video = _fake_video(transcript=existing)

        with patch.object(wf, "is_available", side_effect=AssertionError("no deps")):
            result = wf.ensure_transcript(video, mode="off")

        self.assertFalse(result)
        self.assertEqual(video.transcript, existing)

    def test_auto_with_existing_captions_returns_true_without_deps(self):
        video = _fake_video(transcript=[{"text": "existing"}])

        def _boom():
            raise AssertionError("is_available must not be called when captions exist")

        with patch.object(wf, "is_available", side_effect=_boom):
            result = wf.ensure_transcript(video, mode="auto")

        self.assertTrue(result)
        self.assertEqual(video.transcript, [{"text": "existing"}])

    def test_auto_without_captions_and_missing_deps_raises(self):
        video = _fake_video(transcript=None)
        with patch.object(wf, "is_available", return_value=False):
            with self.assertRaises(wf.MissingDependencyError) as ctx:
                wf.ensure_transcript(video, mode="auto")

        self.assertIn("requirements-whisper.txt", str(ctx.exception))

    def test_auto_without_captions_and_deps_present_transcribes(self):
        video = _fake_video(transcript=None)
        fake_entries = [{"text": "hi", "timestamp": timedelta(0)}]
        captured = {}

        def _fake_download(url, tmpdir, logger):
            captured["tmpdir"] = tmpdir
            return os.path.join(tmpdir, "audio.m4a")

        with patch.object(wf, "is_available", return_value=True), \
             patch.object(wf, "_download_audio", side_effect=_fake_download), \
             patch.object(wf, "_run_whisper", return_value=fake_entries):
            result = wf.ensure_transcript(video, mode="auto")

        self.assertTrue(result)
        self.assertEqual(video.transcript, fake_entries)
        # The temp dir is removed in the finally block.
        self.assertIn("tmpdir", captured)
        self.assertFalse(os.path.exists(captured["tmpdir"]))

    def test_force_with_existing_captions_re_transcribes(self):
        video = _fake_video(transcript=[{"text": "old captions"}])
        fake_entries = [{"text": "new whisper", "timestamp": timedelta(0)}]
        download = MagicMock(return_value="/tmp/fake-audio.m4a")

        with patch.object(wf, "is_available", return_value=True), \
             patch.object(wf, "_download_audio", download), \
             patch.object(wf, "_run_whisper", return_value=fake_entries):
            result = wf.ensure_transcript(video, mode="force")

        self.assertTrue(result)
        download.assert_called_once()
        self.assertEqual(video.transcript, fake_entries)

    def test_invalid_mode_falls_back_to_auto(self):
        video = _fake_video(transcript=[{"text": "existing"}])
        # auto + captions present -> True, no deps touched.
        with patch.object(wf, "is_available", side_effect=AssertionError("no deps")):
            self.assertTrue(wf.ensure_transcript(video, mode="banana"))


class TestRunWhisperTimeout(unittest.TestCase):
    def test_timeout_truncates_and_warns(self):
        """The between-segments deadline stops the loop and logs a warning.

        ``time.monotonic`` is patched with a deterministic sequence so the test
        does not sleep: call 1 sets ``started``; calls 2 and 3 are the checks
        after segment 1 and segment 2. With ``timeout_s=1`` the third check
        (100s elapsed) trips the budget, so only 2 of 3 segments are returned.
        """
        segments = [
            _FakeSegment(0.0, 1.0, "one"),
            _FakeSegment(1.0, 2.0, "two"),
            _FakeSegment(2.0, 3.0, "three"),
        ]
        log = logging.getLogger("test-whisper-timeout")
        log.setLevel(logging.INFO)

        with patch.dict(sys.modules, {"faster_whisper": _install_fake_faster_whisper(segments)}), \
             patch.object(wf.time, "monotonic", side_effect=[0.0, 0.0, 100.0, 100.0]):
            with self.assertLogs(log, level="WARNING") as captured:
                entries = wf._run_whisper(
                    "/tmp/fake.m4a", "small", "de", timeout_s=1.0, logger=log
                )

        self.assertEqual(len(entries), 2)
        self.assertEqual([e["text"] for e in entries], ["one", "two"])
        self.assertTrue(any("budget" in line for line in captured.output))

    def test_no_timeout_returns_all_segments(self):
        segments = [
            _FakeSegment(0.0, 1.0, "one"),
            _FakeSegment(1.0, 2.0, "two"),
        ]
        log = logging.getLogger("test-whisper-notimeout")
        log.setLevel(logging.INFO)

        with patch.dict(sys.modules, {"faster_whisper": _install_fake_faster_whisper(segments)}):
            entries = wf._run_whisper(
                "/tmp/fake.m4a", "small", "de", timeout_s=0, logger=log
            )

        self.assertEqual([e["text"] for e in entries], ["one", "two"])


class TestDownloadAudioFailure(unittest.TestCase):
    def test_yt_dlp_failure_raises_runtime_error(self):
        module = types.ModuleType("yt_dlp")

        class _BoomYDL:
            def __init__(self, *args, **kwargs):
                raise RuntimeError("network exploded")

        module.YoutubeDL = _BoomYDL
        log = logging.getLogger("test-whisper-download")

        with patch.dict(sys.modules, {"yt_dlp": module}):
            with self.assertRaises(RuntimeError) as ctx:
                wf._download_audio("https://youtu.be/x", "/tmp", log)

        self.assertIn("audio download failed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
