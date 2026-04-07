# ---- Stage 1: Build React frontend ----
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# ---- Stage 2: Python runtime ----
FROM python:3.13-slim AS runtime
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend/fringe_shows.csv backend/fringe_performances.csv backend/fringe_venues.csv backend/fringe_shows.geojson ./
COPY backend/main.py backend/embed.py backend/fringe.py ./

# Generates embeddings.npy (~30s, downloads all-MiniLM-L6-v2 model)
RUN uv run python embed.py

COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

EXPOSE 8080
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
