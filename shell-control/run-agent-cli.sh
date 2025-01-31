#!/bin/bash
set -euo pipefail

readonly IMAGE=shell-agent-base
readonly ENV_FILE=.env.openrouter # Configure this!

if [ ! -f "${ENV_FILE}" ]; then
    echo "Error: ${ENV_FILE} not found. Please create it from .env.example" >&2
    exit 1
fi

build() {
    docker build -q --target python-base --tag ${IMAGE} --file agent/Dockerfile ./agent
}

prepare_workdir() {
    readonly WORK_DIR="work/run-$(date +%s)"
    mkdir -p "${WORK_DIR}"

    cp ./agent/backend/*.md "${WORK_DIR}/"
    cp ./agent/backend/*.py "${WORK_DIR}/"
}

interactive() {
    echo "Running in interactive mode. Execute shellcontrol.py manually!"
    docker run --rm -it \
        -v "./${WORK_DIR}:/work" \
        --env-file ${ENV_FILE} \
        --name ${IMAGE} \
        --entrypoint /bin/bash \
        ${IMAGE}
}

auto() {
    readonly PROMPT="$1"
    docker run --rm -it \
        -v "./${WORK_DIR}:/work" \
        --env-file ${ENV_FILE} \
        ${IMAGE} \
        ./shellcontrol.py "${PROMPT}"
}

print_help() {
    echo "Usage: $0 [--interactive | <prompt>]"
    echo "  --interactive       Run the script in interactive mode."
    echo "  <prompt>            Run the script in auto mode with the given prompt (Quote the prompt!)."
    echo "  no parameter        Show this help message."
}

# Main script logic
if [[ "${1:-}" == "--interactive" ]]; then
    build
    prepare_workdir
    interactive
elif [[ -n "${1:-}" ]]; then
    build
    prepare_workdir
    auto "${1}"
else
    print_help
fi
