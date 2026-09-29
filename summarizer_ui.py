# Import necessary libraries
import os
import re
from datetime import date
import streamlit as st
from dotenv import load_dotenv, find_dotenv
# User Defined Libraries
import src.transcribe_summarize as ts
import src.gpt_functions as gpt
from src.config_loader import load_config, get_proxy_settings, get_llm_settings

# Loads .env from the project root (searches upward from this file / CWD)
load_dotenv(find_dotenv(), override=False)

cfg = load_config()
proxy_settings = get_proxy_settings(cfg)
llm_settings = get_llm_settings(cfg)

# --- LLM provider / model selection -------------------------------------------
# Defaults come from config.yml (llm.provider / llm.model). The user can override
# both in the sidebar. For Ollama, models are fetched live from the running
# Ollama server (local or cloud) so the dropdown reflects what's actually
# installed / available. Ollama Cloud is the preferred default.
OPENAI_MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"]
OLLAMA_FALLBACK_MODELS = ["gpt-oss:120b", "gpt-oss:20b", "deepseek-v3", "qwen3:235b"]

st.sidebar.title("LLM Settings")
provider = st.sidebar.selectbox(
    "Provider",
    options=["ollama", "openai"],
    index=0 if llm_settings.provider == "ollama" else 1,
    help="Ollama Cloud is the preferred default. OpenAI uses the OpenAI API.",
)

# Ollama endpoint: Ollama Cloud (preferred) vs. local server
ollama_host = llm_settings.base_url
if provider == "ollama":
    # Default to Ollama Cloud unless the config explicitly points at localhost.
    is_local_configured = "localhost" in ollama_host or "127.0.0.1" in ollama_host
    endpoint = st.sidebar.radio(
        "Ollama endpoint",
        options=["Ollama Cloud (ollama.com)", "Local (localhost:11434)"],
        index=1 if is_local_configured else 0,
        help="Cloud: requires a paid Ollama account + OLLAMA_API_KEY. Local: models installed via `ollama pull`.",
    )
    if endpoint.startswith("Local"):
        ollama_host = "http://localhost:11434"
    else:
        ollama_host = "https://ollama.com"

# Build the model list for the selected provider
if provider == "openai":
    model_options = OPENAI_MODELS
else:
    # Try to fetch the real list of models from the Ollama host.
    probe = llm_settings.__class__(
        provider="ollama",
        base_url=ollama_host,
        model=llm_settings.model,
        model_heavy=llm_settings.model_heavy,
        api_key=(os.getenv("OLLAMA_API_KEY") or os.getenv("API_KEY")) if ollama_host.startswith("https") else None,
    )
    try:
        fetched = gpt.list_ollama_models(probe)
        model_options = fetched if fetched else OLLAMA_FALLBACK_MODELS
        st.sidebar.caption(f"✅ Found {len(model_options)} models on {ollama_host}")
    except Exception as e:
        model_options = OLLAMA_FALLBACK_MODELS
        st.sidebar.caption(f"⚠️ Could not reach Ollama at {ollama_host} ({e}). Showing fallback list.")

default_model = llm_settings.model if provider == llm_settings.provider else model_options[0]
model = st.sidebar.selectbox(
    "Model",
    options=model_options,
    index=model_options.index(default_model) if default_model in model_options else 0,
)

# Allow a custom model name not in the list
custom_model = st.sidebar.text_input("Custom model (optional)", placeholder="e.g. gpt-4o-mini, qwen2.5:7b")
if custom_model.strip():
    model = custom_model.strip()

# Rebuild effective LLM settings from the user's selection
from dataclasses import replace as dc_replace
llm_settings = dc_replace(
    llm_settings,
    provider=provider,
    base_url=ollama_host if provider == "ollama" else llm_settings.base_url,
    model=model,
    model_heavy=model,
)

# Resolve API key based on the selected provider
if provider == "ollama":
    resolved_key = os.getenv("OLLAMA_API_KEY") or os.getenv("API_KEY")
else:
    resolved_key = os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY")
llm_settings = dc_replace(llm_settings, api_key=resolved_key)

# Push the resolved settings into the gpt_functions module so all calls use them
gpt.set_llm_settings(llm_settings)

# Local Ollama servers don't need a key; cloud endpoints do.
needs_key = not ("localhost" in llm_settings.base_url or "127.0.0.1" in llm_settings.base_url)
if needs_key and not llm_settings.api_key:
    st.error(
        f"API key for {provider} not found. "
        f"Please set the {'OLLAMA_API_KEY' if provider == 'ollama' else 'API_KEY'} "
        "environment variable (or Streamlit secrets / .env file)."
    )
    st.stop()

if proxy_settings.enabled and proxy_settings.proxies is None:
    st.error("Proxy is enabled in config.yml, but no proxy URLs are configured.")
    st.stop()

st.title("YouTube Video Summarizer")

# Input for YouTube URL
youtube_url = st.text_input("Enter YouTube URL:")
video = None

# Button to generate summary
if st.button("Clear"):
    for key in st.session_state.keys():
        del st.session_state[key]
    st.rerun()

# Dropdown to select the language of the video
language = st.selectbox("Select the language of the video:", ["English", "Deutsch"], key="video_language")

if st.button("Load Video"):
    if youtube_url:
        # Regular expression to check if the URL is a valid YouTube link
        youtube_regex = re.compile(
            r'^(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/.+$'
        )

        if not youtube_regex.match(youtube_url):
            st.write("Please enter a valid YouTube URL.")
        else:
            with st.spinner('Getting video ...'):
                video = ts.YouTubeVideo(url=youtube_url, proxy=proxy_settings.proxies)
                video.get_data()
                st.session_state.youtube_video = video
                has_description = bool(st.session_state.youtube_video.description)
                has_transcript = bool(st.session_state.youtube_video.transcript)
                if not has_transcript:
                    st.error(
                        "Transcript not available for this video. Please try again. \
                        Opening the Video Transcript in your browser and then trying again may resolve the issue."
                        )
                if st.session_state.youtube_video:
                    st.success("Video retrieved successfully!")
                    st.markdown("### Video Attributes:")
                    st.markdown(f"- **Channel:** {st.session_state.youtube_video.channel}")
                    st.markdown(f"- **Title:** {st.session_state.youtube_video.title}")
                    st.markdown(f"- **Duration:** {st.session_state.youtube_video.duration}")
                    st.markdown(f"- **Description available:** {bool(st.session_state.youtube_video.description)}")
                    st.markdown(f"- **Transcript available:** {bool(st.session_state.youtube_video.transcript)}")
                    st.markdown(f"- **Timestamped Chapters available:** {bool(st.session_state.youtube_video.chapters_available)}")

                else:
                    st.error("Failed to retrieve video. Please try again.")
    else:
        st.write("Please enter a valid YouTube URL.")

# Maintain the state of the second button
if 'youtube_video' in st.session_state and st.session_state.youtube_video:
    col1, col2, col3, col4 = st.columns(4)

    summary_by_chapters_result = None
    summary_entire_video_result = None
    summary_one_sentence_result = None
    shorts_by_chapters_result = None


    with col1:
        if st.button("Summarize by Chapters"):
            with st.spinner('Summarizing video by chapters...'):
                try:
                    summary_by_chapters_result = ts.summary_by_chapters(
                        video=st.session_state.youtube_video,
                        llm=llm_settings
                    )
                except Exception as e:
                    st.error(f"Could not summarize: {e}")

    with col2:
        if st.button("Summarize Entire Video"):
            with st.spinner('Summarizing entire video...'):
                try:
                    summary_entire_video_result = ts.summary_entire_video(
                        video=st.session_state.youtube_video,
                        llm=llm_settings
                    )
                except Exception as e:
                    st.error(f"Could not summarize: {e}")

    with col3:
        if st.button("One Sentence Summary"):
            with st.spinner('Summarizing video in one sentence...'):
                try:
                    summary_one_sentence_result = ts.summary_in_one_sentence(
                        video=st.session_state.youtube_video,
                        llm=llm_settings,
                    )
                except Exception as e:
                    st.error(f"Could not summarize: {e}")

    with col4:
        if st.button("Shorts by Chapters"):
            with st.spinner('Generating ideas for Shorts by chapters...'):
                try:
                    shorts_by_chapters_result = ts.create_shorts_by_chapters(
                        video=st.session_state.youtube_video,
                        llm=llm_settings
                    )
                except Exception as e:
                    st.error(f"Could not generate shorts: {e}")

    if summary_by_chapters_result:
        st.write("Summary by Chapters:")
        st.write(f"### {st.session_state.youtube_video.title}")
        st.write(f"#### by {st.session_state.youtube_video.channel}")
        st.caption(f"Uploaded: {st.session_state.youtube_video.upload_date}  •  Link: {st.session_state.youtube_video.url}  •  Summary created: {date.today().isoformat()}")
        for chapter in summary_by_chapters_result:
            st.write(chapter)

    if shorts_by_chapters_result:
        st.write("Ideas for Shorts by Chapters:")
        st.write(f"### {st.session_state.youtube_video.title}")
        st.write(f"#### by {st.session_state.youtube_video.channel}")
        st.caption(f"Uploaded: {st.session_state.youtube_video.upload_date}  •  Link: {st.session_state.youtube_video.url}  •  Summary created: {date.today().isoformat()}")
        for chapter in shorts_by_chapters_result:
            st.write(chapter)

    if summary_entire_video_result:
        st.write(f"### {st.session_state.youtube_video.title}")
        st.write(f"#### by {st.session_state.youtube_video.channel}")
        st.caption(f"Uploaded: {st.session_state.youtube_video.upload_date}  •  Link: {st.session_state.youtube_video.url}  •  Summary created: {date.today().isoformat()}")
        st.write("Summary of Entire Video:")
        st.write(summary_entire_video_result)

    if summary_one_sentence_result:
        st.write(f"### {st.session_state.youtube_video.title}")
        st.write(f"#### by {st.session_state.youtube_video.channel}")
        st.caption(f"Uploaded: {st.session_state.youtube_video.upload_date}  •  Link: {st.session_state.youtube_video.url}  •  Summary created: {date.today().isoformat()}")
        st.write("One Sentence Summary:")
        st.write(summary_one_sentence_result)
