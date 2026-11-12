#!/usr/bin/env bash
set -euo pipefail

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
runner="$project_dir/daily_transcribe.sh"
if [[ "$runner" == *$'\n'* || "$runner" == *$'\r'* ]]; then
    printf 'Project path cannot contain a newline or carriage return.\n' >&2
    exit 1
fi

quoted_runner=${runner//\'/\'\\\'\'}
quoted_runner=${quoted_runner//%/\\%}
entry="0 2 * * * /bin/sh '$quoted_runner' # voice-transcriber"
crontab_file=$(mktemp)
error_file=$(mktemp)
trap 'rm -f -- "$crontab_file" "$error_file"' EXIT

if ! LC_ALL=C crontab -l > "$crontab_file" 2> "$error_file"; then
    if ! grep -q '^no crontab for ' "$error_file"; then
        cat "$error_file" >&2
        exit 1
    fi
fi

if grep -Fqx -- "$entry" "$crontab_file"; then
    printf 'Daily transcription job is already installed.\n'
    exit 0
fi
printf '%s\n' "$entry" >> "$crontab_file"
crontab "$crontab_file"
printf 'Installed daily transcription job for 02:00 local time.\n'