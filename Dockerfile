# syntax=docker/dockerfile:1

# Stage 1: Build React Frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend

# Install dependencies deterministically via lockfile
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy frontend source files
COPY frontend/tsconfig*.json ./
COPY frontend/vite.config.ts ./
COPY frontend/index.html ./
COPY frontend/public ./public
COPY frontend/src ./src

# Build static production bundle into dist/
RUN npm run build

# Stage 2: Production Python Runtime
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

WORKDIR /app

# Install minimal production Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy verified immutable January 2026 data snapshots
COPY data/ ./data/

# Copy backend application package and root entrypoint
COPY backend/ ./backend/
COPY app.py .

# Copy static frontend build from Stage 1 into /app/frontend/dist
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Expose documented application port
EXPOSE 8000

# Container healthcheck against /api/health
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; sys_exit = 0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').getcode() == 200 else 1; exit(sys_exit)"

# Launch single Uvicorn process serving both API and React SPA
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
