FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install runtime dependencies first for better layer caching.
COPY requirements/base.txt /app/requirements/base.txt
RUN pip install --no-cache-dir -r /app/requirements/base.txt

# Copy application code.
COPY backend /app/backend
COPY config /app/config
COPY scripts /app/scripts
COPY .env.example /app/.env.example

# Ensure runtime data directory exists (SQLite file is created at startup).
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["python", "-m", "backend.main"]
