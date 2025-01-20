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

# Copy backend files
COPY backend/*.py backend/*.md ./

# Copy frontend build from previous stage
COPY --from=frontend /app/frontend/dist/ ./frontend/

EXPOSE 80
ENTRYPOINT ["uvicorn", "shellcontrol-backend:app", "--host", "0.0.0.0", "--port", "80"]
