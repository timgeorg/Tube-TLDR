FROM python:3.12-slim

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY summarizer_ui.py /app
COPY transcribe_summarize.py /app
COPY ./src /app/src
COPY ./Utilities /app/Utilities

CMD ["streamlit", "run", "summarizer_ui.py"]