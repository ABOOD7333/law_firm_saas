#!/bin/sh
set -eu

ollama serve &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true' INT TERM EXIT

attempt=0
until ollama list >/dev/null 2>&1; do
    if ! kill -0 "$server_pid" 2>/dev/null; then
        wait "$server_pid"
        exit 1
    fi
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 60 ]; then
        echo "Ollama did not become ready in time" >&2
        exit 1
    fi
    sleep 2
done

ollama pull "${OLLAMA_MODEL:-qwen2.5:3b}"
wait "$server_pid"
