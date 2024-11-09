import streamlit as st
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
import re

from transcribe_summarize import example_summary



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
    if st.button("Generate Summary"):
        if youtube_url:
            # Regular expression to check if the URL is a valid YouTube link
            youtube_regex = re.compile(
                r'^(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/.+$'
            )

            if not youtube_regex.match(youtube_url):
                st.write("Please enter a valid YouTube URL.")
            else:
                with st.spinner('Generating summary...'):
                    summary = example_summary(youtube_url, st.secrets["API_KEY"])
                st.write("Summary:")
                st.write("Description available:")
                for chapter in summary:
                    st.write(chapter)
        else:
            st.write("Please enter a valid YouTube URL.")