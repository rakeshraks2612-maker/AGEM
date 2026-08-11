FROM python:3.12-slim
WORKDIR /app

# Install deps first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY agem/ ./agem/
COPY config/ ./config/
COPY prompts/ ./prompts/
COPY wsgi.py .

# Set env
ENV PYTHONPATH=/app
ENV PORT=8080

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:$PORT/ || exit 1

EXPOSE 8080
CMD exec gunicorn --bind :$PORT --workers 1 --threads 4 --timeout 300 wsgi:app
