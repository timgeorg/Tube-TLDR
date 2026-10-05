"""
LLM call helpers for the YouTube summarizer.

Supports two backends via LLMSettings.provider:
  - "openai": OpenAI API (openai SDK)
  - "ollama": Ollama Cloud (https://ollama.com) or a local Ollama server (ollama SDK)

All functions accept an optional `llm: LLMSettings` and fall back to the
module-level default set via set_llm_settings().
"""
from __future__ import annotations

import logging
import os
from typing import List, Dict, Optional

from openai import OpenAI

try:
    import ollama
except ImportError:  # ollama is optional; only needed for the "ollama" provider
    ollama = None

try:
    from src.config_loader import LLMSettings
except ImportError:  # when imported as a flat module
    from config_loader import LLMSettings


# Warnings (e.g. empty Ollama responses) go to stderr via the root logger's
# last-resort handler when no handler is configured.
logger = logging.getLogger("gpt_functions")


# Module-level default settings; overridden by set_llm_settings() from the UI/entrypoint.
# Ollama Cloud is the preferred default.
_DEFAULT_LLM = LLMSettings(
    provider="ollama",
    base_url="https://ollama.com",
    model="gpt-oss:120b",
    model_heavy="gpt-oss:120b",
    api_key=os.getenv("OLLAMA_API_KEY") or os.getenv("API_KEY"),
)


def set_llm_settings(settings: LLMSettings) -> None:
    """Set the module-level LLM settings used by all functions in this module."""
    global _DEFAULT_LLM
    _DEFAULT_LLM = settings


# ---------------------------------------------------------------------------
# Backend dispatch
# ---------------------------------------------------------------------------
def _openai_client(s: LLMSettings) -> OpenAI:
    api_key = s.api_key or "ollama"  # local servers may not need a key
    return OpenAI(api_key=api_key, base_url=s.base_url)


def _ollama_client(s: LLMSettings):
    if ollama is None:
        raise RuntimeError(
            "The 'ollama' package is not installed. Install it with: pip install ollama"
        )
    headers = {}
    if s.api_key:
        headers["Authorization"] = f"Bearer {s.api_key}"
    return ollama.Client(host=s.base_url, headers=headers)


def list_ollama_models(s: LLMSettings) -> list[str]:
    """Return the names of models available on the configured Ollama host.

    Works for both a local Ollama server and Ollama Cloud. Raises on connection
    errors so the caller can fall back to a preset list.
    """
    client = _ollama_client(s)
    resp = client.list()
    # SDK returns a pydantic ListResponse; tolerate dict-like too.
    models = getattr(resp, "models", None)
    if models is None and isinstance(resp, dict):
        models = resp.get("models", [])
    names = []
    for m in models or []:
        # Each entry has a .model attribute (name) in the SDK, or "model"/"name" key.
        name = getattr(m, "model", None) or (m.get("model") if isinstance(m, dict) else m.get("name"))
        if name:
            names.append(name)
    return names


def _chat(
    messages: List[Dict[str, str]],
    *,
    model: Optional[str] = None,
    temperature: float = 0.08,
    max_tokens: int = 1024,
    stream: bool = False,
    think: Optional[bool] = None,
    llm: Optional[LLMSettings] = None,
):
    """Unified chat completion dispatcher.

    Returns the full text response (string). When stream=True, consumes the
    stream and returns the concatenated text (so callers don't need to care
    about the backend).

    `think` controls Ollama's thinking/reasoning mode (ignored for OpenAI).
    None means "use the configured default" (LLMSettings.think, which resolves
    to False for Ollama). Reasoning models can otherwise burn the whole
    num_predict budget on internal reasoning and return empty content.
    """
    s = llm or _DEFAULT_LLM
    use_model = model or s.model

    if s.provider == "ollama":
        client = _ollama_client(s)
        # Explicit param wins; otherwise fall back to the configured default.
        effective_think = think if think is not None else (s.think if s.think is not None else False)

        def _ollama_call(think_value: bool):
            kwargs = dict(model=use_model, messages=messages, stream=stream)
            # Ollama uses num_predict instead of max_tokens; map it.
            if max_tokens is not None:
                kwargs["options"] = {"temperature": temperature, "num_predict": max_tokens}
            else:
                kwargs["options"] = {"temperature": temperature}
            try:
                return client.chat(think=think_value, **kwargs)
            except TypeError:
                # Older ollama clients (<0.4) don't accept the `think` kwarg.
                return client.chat(**kwargs)

        def _extract(resp):
            if stream:
                parts = list(resp)
                text = "".join(p["message"]["content"] for p in parts if p.get("message"))
                reason = parts[-1].get("done_reason") if parts else None
                return text, reason
            return resp["message"]["content"], resp.get("done_reason")

        content, done_reason = _extract(_ollama_call(effective_think))
        if not (content or "").strip():
            # Thinking models can exhaust num_predict on reasoning and return
            # empty content with done_reason="length" — silently, no exception.
            logger.warning(
                "Ollama returned empty content (model=%s, done_reason=%s, think=%s); "
                "retrying once with think=False",
                use_model, done_reason, effective_think,
            )
            content, _ = _extract(_ollama_call(False))
        return content

    # Default: OpenAI-compatible
    client = _openai_client(s)
    resp = client.chat.completions.create(
        model=use_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
        stream=stream,
    )
    if stream:
        return "".join(
            chunk.choices[0].delta.content
            for chunk in resp
            if chunk.choices[0].delta.content is not None
        )
    return resp.choices[0].message.content


# ---------------------------------------------------------------------------
# Prompt helpers (one per feature)
# ---------------------------------------------------------------------------
def get_chapter_summary(section: Dict, model: Optional[str] = None, llm: Optional[LLMSettings] = None) -> str:
    """
    Generates a summary for a given section of a video using the configured LLM.
    Model can convert timedelta to string format. (impressive)
    Args:
        section (dict): The section of the video to summarize.
            keys: 'timestamp' (timedelta), 'heading' (str), content (str)
        model (str, optional): Override model. Defaults to the configured model.
        llm (LLMSettings, optional): Explicit settings. Defaults to module settings.
    Returns:
        str: The generated summary of the section.
    """
    return _chat(
        messages=[
            {'role': 'system',
            'content':
                'Summarize the following section of the video. \
                    Use the provided content to generate a summary of the section. \
                    Stay in the original language. \
                    Explain the content short and conversational as a bullet point. \
                    Do not write things like "They mention the importance" or "the speaker says". \
                    If they talk about the 5 things or the 9 types or something like that, list them. \
                    Answer the question thats given in the topic or chapter title if available. \
                    Put the topic with timestamp (in h, min, sec) [if available] in the format "hh:mm:ss" or "mm:ss" as a heading in the format: "Heading Topic (00:34)"\
                    Every Heading should be a markdown ## heading. If there is no heading title (eg. just Chapter 1), create a heading out of the content provided. \
                    Try to keep it as short as possible, but as long as necessary.'},

            {'role': 'user', 'content': str(section)}
        ],
        model=model,
        temperature=0.08,
        max_tokens=1024,
        stream=True,
        llm=llm,
    )


def get_whole_transcript_summary(transcript: str, title: str = "", llm: Optional[LLMSettings] = None) -> str:
    """
    Generates a summary for the entire transcript.
    """
    # Extract a number from the title if present (e.g. "The 50 BEST..." -> 50)
    import re
    numbers_in_title = re.findall(r'\d+', title)
    number_hint = ""
    if numbers_in_title:
        num = numbers_in_title[0]
        number_hint = (
            f" The title contains the number {num}. "
            f"If this number refers to a list of items in the video (e.g., '{num} Best Apps', 'Top {num} Ways', '{num} Things You Should Know'), "
            f"then make sure to list ALL {num} items as bullet points. "
            f"However, if the number is something else (like an age, year, price, or other non-list reference), "
            f"ignore it and summarize the video normally without mentioning the number."
        )

    return _chat(
        messages=[
            {'role': 'system',
            'content':
                'Summarize the following transcript of a video. \
                Use the provided content to generate a summary of the entire video. \
                Stay in the original language. \
                Explain the content in a short, conversational way as bullet points. \
                Do not write things like "They mention the importance" or "the speaker says". \
                If the video discusses lists (e.g., 5 things, 9 types), enumerate them all. \
                If there are questions in the title or main topic, answer them. \
                Try to keep the summary as short as possible, but as long as necessary to cover the main points.' +
                number_hint},

            {'role': 'user', 'content': f"Title: {title}\n\nTranscript: {transcript}"}
        ],
        temperature=0.08,
        max_tokens=2048,
        llm=llm,
    )


def get_one_sentence_summary(transcript: str, title="", llm: Optional[LLMSettings] = None) -> str:
    """
    Generates a one-sentence summary for the entire transcript.
    """
    return _chat(
        messages=[
            {'role': 'system',
            'content':
                'Try to summarize the following transcript in EXACTLY ONE SENTENCE. It can be longer if necessary to conserve information.\
                Here is the available title: ' + title + '\n\n Add the title as a markdown #### heading.'},

            {'role': 'user', 'content': transcript}
        ],
        temperature=0.08,
        max_tokens=1024,
        llm=llm,
    )


def get_minimal_chapter_summary(section: Dict, model: Optional[str] = None, llm: Optional[LLMSettings] = None) -> str:
    return _chat(
        messages=[
            {'role': 'system',
            'content':
                'Summarize the following chapter of a podcast as short as possible in max. 1-2 bullet points.\
                    Stay in the original language. Keep the heading.'},

            {'role': 'user', 'content': str(section)}
        ],
        model=model,
        temperature=0.08,
        max_tokens=256,
        llm=llm,
    )


def get_unified_summary(sections: List[Dict], llm: Optional[LLMSettings] = None) -> str:
    return _chat(
        messages=[
            {'role': 'system',
            'content':
                'Summarize the following outline of a podcast. \
                    Do not only list the topics they talk about, but briefly explain every idea you mention in the summary. \
                    Still try to keep it as short as possible. Use bullet points if possible.'},

            {'role': 'user', 'content': str(sections)}
        ],
        temperature=0.08,
        max_tokens=512,
        llm=llm,
    )


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
    s = llm or _DEFAULT_LLM
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
