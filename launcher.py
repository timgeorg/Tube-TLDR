# launcher.py - Main entry point for the executable

import streamlit.web.cli as stcli
import sys
import os
import webbrowser
import time
import threading
from dotenv import load_dotenv

def open_browser():
    """Wait for server to start, then open browser"""
    time.sleep(3)
    webbrowser.open('http://localhost:8501')

def main():
    from pathlib import Path
    import sys
    import os
    from dotenv import load_dotenv
    import streamlit.web.cli as stcli

    # Some user-level Streamlit configs set global.developmentMode=true, which
    # makes Streamlit assert if --server.port is provided. Force production mode.
    os.environ.setdefault("STREAMLIT_GLOBAL_DEVELOPMENT_MODE", "false")

    # Load external .env (next to exe)
    base_path = Path(sys.executable).parent
    load_dotenv(base_path / ".env")

    # Streamlit app path (bundled)
    if getattr(sys, "frozen", False):
        streamlit_script = os.path.join(sys._MEIPASS, "summarizer_ui.py")
    else:
        streamlit_script = os.path.join(os.path.dirname(__file__), "summarizer_ui.py")

    sys.argv = [
        "streamlit",
        "run",
        streamlit_script,
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
    ]

    sys.exit(stcli.main())


if __name__ == "__main__":
    main()