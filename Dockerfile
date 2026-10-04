FROM python:3.14-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        ffmpeg \
        libinput10 \
        libx11-6 \
        libxkbcommon0 \
        libwayland-client0 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv==0.12.22

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
COPY ui ./ui

RUN uv sync --frozen --no-dev --extra transcription

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data /models \
    && chown -R appuser:appuser /app /data /models

FROM base AS runtime

USER appuser
VOLUME ["/data", "/models"]
ENTRYPOINT ["/app/.venv/bin/subtitle-cli"]

FROM base AS dev

RUN uv sync --frozen --extra transcription
USER appuser
VOLUME ["/data", "/models"]
CMD ["uv", "run", "pytest"]
