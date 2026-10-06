"""Tests for the non-interactive CLI (src/cli.py).

Everything is mocked at the module boundary (src.cli.YouTubeVideo, src.cli.ts,
src.cli.gpt) so no test touches the network or an LLM. The hard invariant under
test is stdout purity: only the summary (or the JSON payload) may ever reach
stdout — all progress and errors go to stderr.
"""
# Let Python locate the source code
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
import unittest
from datetime import timedelta
from unittest.mock import MagicMock, patch

import src.cli as cli
from src.config_loader import LLMSettings


def _make_video(
    title="Test Video",
    channel="Test Channel",
    chapters_available=True,
    transcript=None,
):
    """Build a stand-in for a fetched YouTubeVideo."""
    video = MagicMock()
    video.url = "https://www.youtube.com/watch?v=test"
    video.title = title
    video.channel = channel
    video.upload_date = "2026-01-01"
    video.duration = timedelta(minutes=10, seconds=30)
    video.transcript = (
        transcript if transcript is not None else [{"text": "hello", "timestamp": timedelta(0)}]
    )
    video.chapters_available = chapters_available
    video.chapters = [{"timestamp": "0:00", "content": "Intro"}] if chapters_available else None
    return video


def _configured_llm():
    """A local Ollama settings object that counts as configured (no API key needed)."""
    return LLMSettings(
        provider="ollama",
        base_url="http://localhost:11434",
        model="test-model",
        model_heavy="test-model",
        api_key=None,
    )


class _CliTestBase(unittest.TestCase):
    """Patch the network fetch, the LLM settings, and the summary functions."""

    def setUp(self):
        self.video = _make_video()

        self._patches = [
            patch.object(cli, "YouTubeVideo", return_value=self.video),
            patch.object(cli, "get_llm_settings", return_value=_configured_llm()),
            patch.object(cli, "get_proxy_settings", return_value=MagicMock(enabled=False, proxies=None)),
            patch.object(cli, "load_config", return_value={}),
            patch.object(cli.gpt, "set_llm_settings"),
            patch.object(cli.ts, "summary_entire_video", return_value="- point one\n- point two"),
            patch.object(cli.ts, "summary_in_one_sentence", return_value="One sentence."),
            patch.object(cli.ts, "summary_by_chapters", return_value=["Chapter A", "Chapter B"]),
            patch.object(
                cli.shorts,
                "create_shorts_by_chapters",
                return_value=[{"heading": "Intro", "script": "Hook line."}],
            ),
            # The optional Whisper fallback is a no-op here: these tests exercise
            # the CLI wiring, not the fallback itself (see test_whisper_fallback.py
            # and TestTranscriptSource below). Without this patch a caption-less
            # video would hit the real dependency check and exit 1 instead of 3.
            patch.object(cli.whisper_fallback, "ensure_transcript", return_value=True),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)


class TestStdoutPurity(_CliTestBase):
    def test_default_style_prints_summary_to_stdout_only(self):
        import io
        from contextlib import redirect_stdout, redirect_stderr

        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["https://www.youtube.com/watch?v=test"])

        self.assertEqual(code, 0)
        # stdout is exactly the rendered summary (header + body), nothing else.
        self.assertIn("## Test Video", out.getvalue())
        self.assertIn("- point one", out.getvalue())
        self.assertTrue(out.getvalue().startswith("## Test Video"))
        # progress went to stderr
        self.assertIn("Fetching video", err.getvalue())
        self.assertIn("Summarizing entire video", err.getvalue())

    def test_stdout_has_no_progress_lines(self):
        import io
        from contextlib import redirect_stdout, redirect_stderr

        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            cli.main(["https://www.youtube.com/watch?v=test"])

        for noisy in ("Fetching video", "Summarizing", "Wrote ", "INFO"):
            self.assertNotIn(noisy, out.getvalue())


class TestFileOutput(_CliTestBase):
    def test_out_writes_file_and_keeps_stdout_empty(self, ):
        import io
        import tempfile
        from contextlib import redirect_stdout, redirect_stderr
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "nested" / "summary.md"
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = cli.main(
                    ["https://www.youtube.com/watch?v=test", "--out", str(target)]
                )

            self.assertEqual(code, 0)
            self.assertEqual(out.getvalue(), "")
            self.assertTrue(target.exists())
            self.assertIn("## Test Video", target.read_text(encoding="utf-8"))
            self.assertIn("Wrote", err.getvalue())

    def test_out_logs_overwrite_of_existing_file(self):
        import io
        import tempfile
        from contextlib import redirect_stdout, redirect_stderr
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "summary.md"
            target.write_text("old content", encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                cli.main(["https://www.youtube.com/watch?v=test", "--out", str(target)])

            self.assertIn("Overwriting existing", err.getvalue())
            self.assertIn("## Test Video", target.read_text(encoding="utf-8"))


class TestJsonOutput(_CliTestBase):
    def test_json_payload_has_expected_keys(self):
        import io
        from contextlib import redirect_stdout, redirect_stderr

        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["https://www.youtube.com/watch?v=test", "--json"])

        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        for key in ("url", "title", "channel", "uploaded", "duration_seconds", "style", "chars"):
            self.assertIn(key, payload)
        self.assertEqual(payload["title"], "Test Video")
        self.assertEqual(payload["style"], "entire")
        self.assertEqual(payload["duration_seconds"], 630.0)
        self.assertIn("summary_text", payload)
        self.assertNotIn("summary_items", payload)

    def test_json_chapters_uses_summary_items(self):
        import io
        from contextlib import redirect_stdout, redirect_stderr

        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            cli.main(["https://www.youtube.com/watch?v=test", "--style", "chapters", "--json"])

        payload = json.loads(out.getvalue())
        self.assertEqual(payload["summary_items"], ["Chapter A", "Chapter B"])
        self.assertNotIn("summary_text", payload)


class TestChaptersJoin(_CliTestBase):
    def test_chapters_list_joined_as_paragraphs(self):
        import io
        from contextlib import redirect_stdout, redirect_stderr

        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            cli.main(["https://www.youtube.com/watch?v=test", "--style", "chapters"])

        body = out.getvalue().split("**Summary created:**")[1]
        self.assertIn("Chapter A\n\nChapter B", body)


class TestShorts(_CliTestBase):
    def test_shorts_without_chapters_exits_3(self):
        import io
        from contextlib import redirect_stdout, redirect_stderr

        self.video.chapters_available = False
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["https://www.youtube.com/watch?v=test", "--style", "shorts"])

        self.assertEqual(code, 3)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("chapter markers", err.getvalue())

    def test_shorts_with_chapters_renders_numbered_list(self):
        import io
        from contextlib import redirect_stdout, redirect_stderr

        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["https://www.youtube.com/watch?v=test", "--style", "shorts"])

        self.assertEqual(code, 0)
        self.assertIn("1. **Intro**", out.getvalue())
        self.assertIn("Hook line.", out.getvalue())


class TestLanguageForwarding(_CliTestBase):
    def test_language_comma_split_forwarded_to_get_data(self):
        import io
        from contextlib import redirect_stdout, redirect_stderr

        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            cli.main(["https://www.youtube.com/watch?v=test", "--language", "de,en"])

        self.video.get_data.assert_called_once_with(languages=["de", "en"])

    def test_no_language_passes_none(self):
        import io
        from contextlib import redirect_stdout, redirect_stderr

        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            cli.main(["https://www.youtube.com/watch?v=test"])

        self.video.get_data.assert_called_once_with(languages=None)


class TestExitCodes(_CliTestBase):
    def test_fetch_failure_exits_3(self):
        import io
        from contextlib import redirect_stdout, redirect_stderr

        self.video.get_data.side_effect = RuntimeError("boom")
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["https://www.youtube.com/watch?v=test"])

        self.assertEqual(code, 3)
        self.assertIn("Failed to fetch video", err.getvalue())

    def test_missing_transcript_exits_3(self):
        import io
        from contextlib import redirect_stdout, redirect_stderr

        self.video.transcript = None
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["https://www.youtube.com/watch?v=test"])

        self.assertEqual(code, 3)
        self.assertIn("No transcript available", err.getvalue())

    def test_summarize_exception_exits_4(self):
        import io
        from contextlib import redirect_stdout, redirect_stderr

        cli.ts.summary_entire_video.side_effect = RuntimeError("llm down")
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["https://www.youtube.com/watch?v=test"])

        self.assertEqual(code, 4)
        self.assertIn("Summarization failed", err.getvalue())

    def test_unconfigured_llm_exits_1(self):
        import io
        from contextlib import redirect_stdout, redirect_stderr

        unconfigured = LLMSettings(
            provider="ollama",
            base_url="https://ollama.com",
            model="gpt-oss:120b",
            model_heavy="gpt-oss:120b",
            api_key=None,
        )
        with patch.object(cli, "get_llm_settings", return_value=unconfigured):
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = cli.main(["https://www.youtube.com/watch?v=test"])

        self.assertEqual(code, 1)
        self.assertIn("OLLAMA_API_KEY", err.getvalue())

    def test_proxy_enabled_but_unset_exits_1(self):
        import io
        from contextlib import redirect_stdout, redirect_stderr

        with patch.object(
            cli, "get_proxy_settings", return_value=MagicMock(enabled=True, proxies=None)
        ):
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = cli.main(["https://www.youtube.com/watch?v=test"])

        self.assertEqual(code, 1)
        self.assertIn("Proxy is enabled", err.getvalue())

    def test_timeout_deadline_exits_2(self):
        import io
        from contextlib import redirect_stdout, redirect_stderr

        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            # First monotonic() call sets the deadline (0.0 + 1s); the next call
            # at the fetch stage is already past it.
            with patch.object(cli.time, "monotonic", side_effect=[0.0, 100.0, 100.0]):
                code = cli.main(["https://www.youtube.com/watch?v=test", "--timeout", "1"])

        self.assertEqual(code, 2)
        self.assertIn("Timeout deadline exceeded", err.getvalue())


class TestConfigOverride(unittest.TestCase):
    """Verify the --config mechanism against the *real* config loader.

    src.config_loader._default_config_path() reads CONFIG_PATH at call time, so
    setting os.environ["CONFIG_PATH"] at the top of main() is sufficient. This
    test proves the resolution order rather than assuming it.
    """

    def test_config_flag_sets_env_and_loader_sees_it(self):
        import io
        import tempfile
        from contextlib import redirect_stdout, redirect_stderr
        from pathlib import Path

        from src.config_loader import load_config as real_load_config

        video = _make_video()
        seen = {}

        def _spy_load_config(*args, **kwargs):
            seen["cfg"] = real_load_config(*args, **kwargs)
            return seen["cfg"]

        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = Path(tmp) / "config.yml"
            cfg_path.write_text(
                "llm:\n"
                "  provider: ollama\n"
                "  base_url: http://localhost:11434\n"
                "  model: test-model\n"
                "proxy:\n"
                "  enabled: false\n",
                encoding="utf-8",
            )

            old_env = os.environ.get("CONFIG_PATH")
            try:
                with patch.object(cli, "YouTubeVideo", return_value=video), \
                     patch.object(cli, "load_config", side_effect=_spy_load_config), \
                     patch.object(cli, "get_proxy_settings", return_value=MagicMock(enabled=False, proxies=None)), \
                     patch.object(cli.gpt, "set_llm_settings"), \
                     patch.object(cli.ts, "summary_entire_video", return_value="ok"):
                    out, err = io.StringIO(), io.StringIO()
                    with redirect_stdout(out), redirect_stderr(err):
                        code = cli.main(
                            ["https://www.youtube.com/watch?v=test", "--config", str(cfg_path)]
                        )

                self.assertEqual(code, 0)
                # The env var was set before load_config ran ...
                self.assertEqual(os.environ["CONFIG_PATH"], str(cfg_path))
                # ... and the real loader resolved the temp file, not the repo config.
                self.assertEqual(seen["cfg"]["llm"]["provider"], "ollama")
                self.assertEqual(seen["cfg"]["llm"]["base_url"], "http://localhost:11434")
                self.assertEqual(seen["cfg"]["llm"]["model"], "test-model")
            finally:
                if old_env is None:
                    os.environ.pop("CONFIG_PATH", None)
                else:
                    os.environ["CONFIG_PATH"] = old_env


class TestTranscriptSource(_CliTestBase):
    """--transcript-source flag → whisper mode mapping + exit codes.

    The mapping lives in ``cli._resolve_transcript_mode`` (read it: captions→off,
    whisper→auto, force-whisper→force, auto→config fallback). These tests assert
    the *actual* mapping and the CLI's error handling around the fallback.
    """

    def setUp(self):
        super().setUp()
        # Replace the base's no-op with an inspectable mock.
        self.ensure = MagicMock(return_value=True)
        patcher = patch.object(cli.whisper_fallback, "ensure_transcript", self.ensure)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _run(self, argv):
        import io
        from contextlib import redirect_stdout, redirect_stderr

        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_force_whisper_maps_to_mode_force(self):
        code, _, _ = self._run(
            ["https://www.youtube.com/watch?v=test", "--transcript-source", "force-whisper"]
        )
        self.assertEqual(code, 0)
        self.assertEqual(self.ensure.call_args.kwargs["mode"], "force")

    def test_captions_maps_to_mode_off(self):
        code, _, _ = self._run(
            ["https://www.youtube.com/watch?v=test", "--transcript-source", "captions"]
        )
        self.assertEqual(code, 0)
        self.assertEqual(self.ensure.call_args.kwargs["mode"], "off")

    def test_whisper_maps_to_mode_auto(self):
        code, _, _ = self._run(
            ["https://www.youtube.com/watch?v=test", "--transcript-source", "whisper"]
        )
        self.assertEqual(code, 0)
        self.assertEqual(self.ensure.call_args.kwargs["mode"], "auto")

    def test_auto_defers_to_config_fallback(self):
        with patch.object(cli, "load_config", return_value={"transcription": {"fallback": "off"}}):
            code, _, _ = self._run(
                ["https://www.youtube.com/watch?v=test", "--transcript-source", "auto"]
            )
        self.assertEqual(code, 0)
        self.assertEqual(self.ensure.call_args.kwargs["mode"], "off")

    def test_default_flag_is_auto(self):
        code, _, _ = self._run(["https://www.youtube.com/watch?v=test"])
        self.assertEqual(code, 0)
        self.assertEqual(self.ensure.call_args.kwargs["mode"], "auto")

    def test_missing_dependency_exits_1_with_hint(self):
        self.ensure.side_effect = cli.whisper_fallback.MissingDependencyError(
            "Local transcription fallback requires optional dependencies. "
            "Install them with: pip install -r requirements-whisper.txt"
        )
        code, out, err = self._run(
            ["https://www.youtube.com/watch?v=test", "--transcript-source", "force-whisper"]
        )
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("requirements-whisper.txt", err)

    def test_runtime_error_exits_3(self):
        self.ensure.side_effect = RuntimeError("audio download failed: boom")
        code, out, err = self._run(
            ["https://www.youtube.com/watch?v=test", "--transcript-source", "force-whisper"]
        )
        self.assertEqual(code, 3)
        self.assertEqual(out, "")
        self.assertIn("audio download failed", err)

    def test_captions_present_with_mode_off_keeps_captions(self):
        """captions→off + captions present: ensure_transcript is a harmless no-op.

        The real ensure_transcript returns False for mode=off without touching
        the video; here the mock returns True, so we assert the *flow*: the CLI
        still summarizes using the existing captions and exits 0.
        """
        self.video.transcript = [{"text": "existing", "timestamp": timedelta(0)}]
        code, out, _ = self._run(
            ["https://www.youtube.com/watch?v=test", "--transcript-source", "captions"]
        )
        self.assertEqual(code, 0)
        self.assertIn("## Test Video", out)
        self.assertEqual(self.ensure.call_args.kwargs["mode"], "off")


if __name__ == "__main__":
    unittest.main()
