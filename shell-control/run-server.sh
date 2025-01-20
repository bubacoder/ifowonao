#!/bin/sh
set -e

IMAGE=shell-control-web
ENV_FILE=.env.litellm

# For detailed messages / debugging, add: --no-cache --progress=plain
docker build -t ${IMAGE} .
docker run --rm -it --env-file ${ENV_FILE} --name ${IMAGE} --net=host ${IMAGE}
