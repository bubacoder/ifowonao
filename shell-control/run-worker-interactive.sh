#!/bin/bash
set -euo pipefail

readonly WORK_DIR=work
mkdir -p "${WORK_DIR}"

cp ./backend/*.md "${WORK_DIR}/"
cp ./backend/*.py "${WORK_DIR}/"

readonly IMAGE=python-shell-control-worker-base
readonly ENV_FILE=.env.openrouter

docker build -q --target worker-base -t ${IMAGE} .
docker run --rm -it -v ./work:/work --env-file ${ENV_FILE} --entrypoint /bin/bash ${IMAGE}
