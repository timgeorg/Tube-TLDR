# Import necessary libraries
import re
import streamlit as st
# User Defined Libraries
import src.transcribe_summarize as ts

st.title("YouTube Video Summarizer")

# Input for YouTube URL
youtube_url = st.text_input("Enter YouTube URL:")
video = None

# Button to generate summary
if st.button("Clear"):
    for key in st.session_state.keys():
        del st.session_state[key]
    st.rerun()

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
                video = ts.YouTubeVideo(url=youtube_url)
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

    with col1:
        if st.button("Summarize by Chapters"):
            with st.spinner('Summarizing video by chapters...'):
                summary_by_chapters_result = ts.summary_by_chapters(
                    video=st.session_state.youtube_video, 
                    api_key=st.secrets["API_KEY"]
                )

    with col2:
        if st.button("Summarize Entire Video"):
            with st.spinner('Summarizing entire video...'):
                summary_entire_video_result = ts.summary_entire_video(
                    url=st.session_state.youtube_video.url, 
                    api_key=st.secrets["API_KEY"]
                )

    with col3:
        if st.button("One Sentence Summary"):
            with st.spinner('Summarizing video in one sentence...'):
                summary_one_sentence_result = ts.summary_in_one_sentence(
                    url=st.session_state.youtube_video.url, 
                    api_key=st.secrets["API_KEY"], 
                )

    with col4:
        if st.button("Option 4"):
            st.write("Option 4 selected")

    if summary_by_chapters_result:
        st.write("Summary by Chapters:")
        st.write(f"### {st.session_state.youtube_video.title}")
        st.write(f"#### by {st.session_state.youtube_video.channel}")
        for chapter in summary_by_chapters_result:
            st.write(chapter)

    if summary_entire_video_result:
        st.write("Summary of Entire Video:")
        st.write(summary_entire_video_result)

    if summary_one_sentence_result:
        st.write("One Sentence Summary:")
        st.write(summary_one_sentence_result)
