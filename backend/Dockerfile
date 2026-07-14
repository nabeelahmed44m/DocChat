# Doc Chat backend — production image
FROM python:3.11-slim AS base

# System deps: tesseract for OCR, plus the runtime libs PyMuPDF/Pillow need.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DOCCHAT_STORAGE_DIR=/app/data

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app ./app

# Scratch dir for uploads-in-flight; durable state lives in Postgres + R2.
# (No VOLUME instruction — Railway rejects it; attach a Railway Volume at
# /app/data instead if you ever need persistent local storage.)
RUN mkdir -p /app/data

EXPOSE 8000

# Shell form so ${PORT} expands — Railway/Render inject the port to bind.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
