FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y git curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN echo "cache-buster-20260815-full-holes-fix-v5"

COPY agem/ ./agem/
COPY static/ ./static/
COPY config/ ./config/
COPY prompts/ ./prompts/
COPY wsgi.py .

# Initialize baseline Git repo for branch isolation in Cloud Run
RUN git config --global user.name "AGEM Autonomous Agent" && \
    git config --global user.email "agent@agem.ai" && \
    git config --global init.defaultBranch main && \
    git init && \
    git add . && \
    git commit -m "chore: baseline infrastructure state for AGEM optimization loop"

ENV PYTHONPATH=/app
ENV PORT=8080

EXPOSE 8080
CMD exec gunicorn --bind :$PORT --workers 1 --threads 4 --timeout 300 wsgi:app
