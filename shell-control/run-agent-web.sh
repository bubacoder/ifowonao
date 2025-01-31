#!/bin/bash
set -euo pipefail

readonly IMAGE=shell-agent-web
readonly ENV_FILE=.env.openrouter # Configure this!

if [ ! -f "${ENV_FILE}" ]; then
    echo "Error: ${ENV_FILE} not found. Please create it from .env.example" >&2
    exit 1
fi

# For detailed messages / debugging, add: --no-cache --progress=plain
docker build --tag ${IMAGE} --file agent/Dockerfile ./agent
docker run --rm -it \
    --env-file ${ENV_FILE} \
    --name ${IMAGE} \
    --net=host ${IMAGE}
