# Minimal image for the API. Runs the demo store with no external deps,
# so it deploys and serves /ask immediately.
FROM python:3.11-slim

# Link the GHCR package back to the repo and license.
LABEL org.opencontainers.image.source="https://github.com/yjkong04/central-dogma"
LABEL org.opencontainers.image.description="Multi-modal RAG over scientific papers: cited answers over text and figures"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Deps first for layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ ./api/

EXPOSE 8000

# Honor the platform's $PORT (Fly/Render inject it); default to 8000 locally.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
