# Stage 1: Builder
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install uv for fast, reproducible dependency resolution
RUN pip install uv

# Production dependencies (sync with pyproject.toml)
RUN uv pip install \
    "streamlit>=1.54.0,<2.0.0" \
    "pandas>=2.0.0" \
    "numpy>=1.24.0" \
    "plotly>=5.18.0" \
    "httpx>=0.27.0" \
    "sqlalchemy>=2.0.0" \
    "streamlit-extras>=1.5.0"

# Stage 2: Runtime
FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl sqlite3 qrencode \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN useradd --create-home --uid 1000 streamlit
USER streamlit
WORKDIR /app

COPY --chown=streamlit:streamlit . .

RUN mkdir -p /app/data

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", \
    "--server.port=8501", \
    "--server.address=0.0.0.0"]
