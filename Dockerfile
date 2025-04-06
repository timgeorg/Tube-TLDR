FROM python:3.12-slim

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt

COPY summarizer_ui.py /app/summarizer_ui.py
COPY ./src /app/src
COPY .streamlit /app/.streamlit
COPY config.yaml /app/config.yaml

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit", "run", "summarizer_ui.py", "--server.port=8501", "--server.address=0.0.0.0"]

# Build-Command:
# docker build -t tube_summary:latest .