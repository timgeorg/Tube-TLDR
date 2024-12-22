import streamlit as st
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
import re

from transcribe_summarize import example_summary, get_video


with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)
# Pre-hashing all plain text passwords once
stauth.Hasher.hash_passwords(config['credentials'])


authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

authenticator.login()

if st.session_state['authentication_status'] is False:
    st.error('Username/password is incorrect')
elif st.session_state['authentication_status'] is None:
    st.warning('Please enter your username and password')

elif st.session_state['authentication_status']:
    authenticator.logout()
    st.write(f'Welcome *{st.session_state["name"]}*')

    st.title("YouTube Video Summarizer")

    # Input for YouTube URL
    youtube_url = st.text_input("Enter YouTube URL:")

    # Button to generate summary
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
                    st.session_state.youtube_video = get_video(youtube_url)
                    has_description = bool(st.session_state.youtube_video.description)
                    has_transcript = bool(st.session_state.youtube_video.transcript)
                    if not has_transcript:
                        st.error(
                            "Transcript not available for this video. Please try again. \
                            Opening the Video Transript in your browser and then trying again may resolve the issue."
                            )
                    if st.session_state.youtube_video:
                        st.success("Video retrieved successfully!")
                        st.markdown("### Video Attributes:")
                        st.markdown(f"- **Channel:** {st.session_state.youtube_video.channel}")
                        st.markdown(f"- **Title:** {st.session_state.youtube_video.title}")
                        st.markdown(f"- **Duration:** {st.session_state.youtube_video.duration}")
                        st.markdown(f"- **Description available:** {bool(st.session_state.youtube_video.description)}")
                        st.markdown(f"- **Transcript available:** {bool(st.session_state.youtube_video.transcript)}")

                    

                    else:
                        st.error("Failed to retrieve video. Please try again.")
        else:
            st.write("Please enter a valid YouTube URL.")

    # Maintain the state of the second button
    if 'youtube_video' in st.session_state and st.session_state.youtube_video:
        if st.button("Summarize"):
            with st.spinner('Summarizing video ...'):
                summary = example_summary(st.session_state.youtube_video.url, st.secrets["API_KEY"])
                st.write("Summary:")
                for chapter in summary:
                    st.write(chapter)