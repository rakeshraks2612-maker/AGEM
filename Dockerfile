FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y git curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agem/ ./agem/
COPY config/ ./config/
COPY prompts/ ./prompts/
COPY wsgi.py .

ENV PYTHONPATH=/app
ENV PORT=8080

EXPOSE 8080
CMD exec gunicorn --bind :$PORT --workers 1 --threads 4 --timeout 300 wsgi:app
