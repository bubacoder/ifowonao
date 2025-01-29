# --- Frontend (Vue.js) ---
FROM node:23-alpine3.20 AS frontend
WORKDIR /app/frontend

# Install dependencies first (cache this layer if package.json doesn't change)
COPY frontend/package*.json ./
RUN npm clean-install

# Copy and build
COPY frontend/ ./
RUN npm run build


# --- Worker base with dependencies installed ---
FROM python:3.13-bookworm AS worker-base

WORKDIR /work

# Dpkg configuration to reduce detailed output
COPY backend/docker/apt-conf /etc/apt/apt.conf.d/99quiet

# Install dependencies
RUN apt-get update
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# --- Backend (FastAPI) and frontend combined ---
FROM worker-base AS webserver

WORKDIR /work

ARG PORT=8008
ARG WORKERS=1

# Reference: https://www.uvicorn.org/settings/
ENV UVICORN_PORT=${PORT}
ENV UVICORN_WORKERS=${WORKERS}

# Copy backend files
COPY backend/*.py backend/*.md ./

# Copy frontend build from previous stage
COPY --from=frontend /app/frontend/dist/ ./frontend/

# Set up health check
HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl --fail http://localhost:${UVICORN_PORT}/health || exit 1

EXPOSE ${PORT}
ENTRYPOINT ["uvicorn", "shellcontrol-backend:app", "--host", "0.0.0.0"]
