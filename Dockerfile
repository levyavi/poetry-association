FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY . /app

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip setuptools wheel \
    && /opt/venv/bin/pip install -e . \
    && /opt/venv/bin/python scripts/download_model.py

ENV PATH="/opt/venv/bin:$PATH"

CMD ["sh", "-c", "gunicorn \"poem_assoc:create_app()\" --bind 0.0.0.0:${PORT} --workers 1 --threads 2 --timeout 180"]
