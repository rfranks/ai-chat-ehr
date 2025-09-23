#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH:-}"

PROMPT_CATALOG_PORT="${PROMPT_CATALOG_PORT:-8001}"
PATIENT_CONTEXT_PORT="${PATIENT_CONTEXT_PORT:-8002}"
CHAIN_EXECUTOR_PORT="${CHAIN_EXECUTOR_PORT:-8003}"
HOST="${HOST:-0.0.0.0}"

pids=()

start_service() {
    local module_path="$1"
    local port="$2"
    local label="$3"

    echo "Starting ${label} on ${HOST}:${port}"
    python -m uvicorn "${module_path}:app" \
        --host "${HOST}" \
        --port "${port}" \
        --reload \
        --reload-dir "${ROOT_DIR}" &
    pids+=("$!")
}

cleanup() {
    for pid in "${pids[@]}"; do
        if kill -0 "${pid}" >/dev/null 2>&1; then
            kill "${pid}" >/dev/null 2>&1 || true
        fi
    done
}

trap cleanup EXIT INT TERM

start_service "services.prompt_catalog.main" "${PROMPT_CATALOG_PORT}" "Prompt Catalog service"
start_service "services.patient_context.main" "${PATIENT_CONTEXT_PORT}" "Patient Context service"
start_service "services.chain_executor.main" "${CHAIN_EXECUTOR_PORT}" "Chain Executor service"

echo "All services started. Press Ctrl+C to stop."
wait "${pids[@]}"
