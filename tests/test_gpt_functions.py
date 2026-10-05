# Let Python locate the source code
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from unittest.mock import patch, MagicMock

from src.config_loader import LLMSettings
import src.gpt_functions as gpt


def _ollama_settings(think=None):
    """Build Ollama LLMSettings for the tests."""
    return LLMSettings(
        provider="ollama",
        base_url="http://localhost:11434",
        model="deepseek-v4.1-flash:cloud",
        model_heavy="deepseek-v4.1-flash:cloud",
        api_key=None,
        think=think,
    )


def _resp(content, done_reason="stop"):
    """Minimal Ollama chat response (dict supports both [] and .get())."""
    return {"message": {"role": "assistant", "content": content}, "done_reason": done_reason}


class TestChatOllamaThink(unittest.TestCase):
    """_chat forwards the thinking flag to the Ollama client."""

    def test_passes_think_false_by_default(self):
        client = MagicMock()
        client.chat.return_value = _resp("hello")
        with patch("src.gpt_functions._ollama_client", return_value=client):
            out = gpt._chat([{"role": "user", "content": "hi"}], llm=_ollama_settings())
        self.assertEqual(out, "hello")
        self.assertEqual(client.chat.call_args.kwargs.get("think"), False)

    def test_explicit_think_true_is_forwarded(self):
        client = MagicMock()
        client.chat.return_value = _resp("hello")
        with patch("src.gpt_functions._ollama_client", return_value=client):
            gpt._chat([{"role": "user", "content": "hi"}], think=True, llm=_ollama_settings())
        self.assertEqual(client.chat.call_args.kwargs.get("think"), True)

    def test_config_think_true_is_used(self):
        client = MagicMock()
        client.chat.return_value = _resp("hello")
        with patch("src.gpt_functions._ollama_client", return_value=client):
            gpt._chat([{"role": "user", "content": "hi"}], llm=_ollama_settings(think=True))
        self.assertEqual(client.chat.call_args.kwargs.get("think"), True)


class TestChatEmptyResponseGuard(unittest.TestCase):
    """Empty Ollama content triggers one retry with think=False."""

    def test_empty_first_call_retries_with_think_false(self):
        client = MagicMock()
        client.chat.side_effect = [_resp("", done_reason="length"), _resp("recovered")]
        with patch("src.gpt_functions._ollama_client", return_value=client):
            with self.assertLogs("gpt_functions", level="WARNING") as cm:
                out = gpt._chat([{"role": "user", "content": "hi"}], llm=_ollama_settings(think=True))
        self.assertEqual(out, "recovered")
        self.assertEqual(client.chat.call_count, 2)
        # First call honoured the configured think=True; the retry forced False.
        self.assertEqual(client.chat.call_args_list[0].kwargs.get("think"), True)
        self.assertEqual(client.chat.call_args_list[1].kwargs.get("think"), False)
        self.assertTrue(any("empty content" in m for m in cm.output))

    def test_both_empty_returns_empty_no_loop(self):
        client = MagicMock()
        client.chat.side_effect = [_resp("", done_reason="length"), _resp("", done_reason="length")]
        with patch("src.gpt_functions._ollama_client", return_value=client):
            with self.assertLogs("gpt_functions", level="WARNING"):
                out = gpt._chat([{"role": "user", "content": "hi"}], llm=_ollama_settings())
        self.assertEqual(out, "")
        self.assertEqual(client.chat.call_count, 2)

    def test_whitespace_only_counts_as_empty(self):
        client = MagicMock()
        client.chat.side_effect = [_resp("   \n"), _resp("ok")]
        with patch("src.gpt_functions._ollama_client", return_value=client):
            with self.assertLogs("gpt_functions", level="WARNING"):
                out = gpt._chat([{"role": "user", "content": "hi"}], llm=_ollama_settings())
        self.assertEqual(out, "ok")
        self.assertEqual(client.chat.call_count, 2)


class TestChatOllamaThinkFallback(unittest.TestCase):
    """Older ollama clients that reject `think` still work."""

    def test_typeerror_on_think_retries_without_kwarg(self):
        client = MagicMock()

        def chat(**kwargs):
            if "think" in kwargs:
                raise TypeError("chat() got an unexpected keyword argument 'think'")
            return _resp("legacy ok")

        client.chat.side_effect = chat
        with patch("src.gpt_functions._ollama_client", return_value=client):
            out = gpt._chat([{"role": "user", "content": "hi"}], llm=_ollama_settings())
        self.assertEqual(out, "legacy ok")
        self.assertEqual(client.chat.call_count, 2)


if __name__ == '__main__':
    unittest.main()
