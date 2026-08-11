FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY agem/ ./agem/
COPY config/ ./config/
COPY prompts/ ./prompts/
CMD ["python", "-m", "agem.profiler"]
