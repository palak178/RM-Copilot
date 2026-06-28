# Forward-looking image for the reproducible demo (Streamlit UI).
# Builds the full app once code lands; safe to build now (installs deps only).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependency metadata first for better layer caching.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install ".[llm,seed,ui]"

# Application sources (UI adapters, scripts, prompts, config).
COPY ui ./ui
COPY scripts ./scripts
COPY prompts ./prompts
COPY config ./config

# Non-root runtime user.
RUN useradd --create-home --uid 10001 appuser && \
    mkdir -p /app/var && chown -R appuser:appuser /app
USER appuser

EXPOSE 8501

# Default: launch the Streamlit demo. Override CMD for the CLI or seeding.
CMD ["streamlit", "run", "ui/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
