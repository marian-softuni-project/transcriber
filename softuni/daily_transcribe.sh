#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
PYTHONPATH="$PROJECT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
export PATH PYTHONPATH

if [ -x "$PROJECT_DIR/.venv/bin/python" ]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"
else
    PYTHON=python3
fi

exec "$PYTHON" -m voice_transcriber.cli \
    --database "$PROJECT_DIR/transcriptions.db" \
    --directory "$PROJECT_DIR/data" >> "$PROJECT_DIR/transcriptions.log" 2>&1