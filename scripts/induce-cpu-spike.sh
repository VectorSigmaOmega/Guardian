#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <ssh-host> [duration-seconds]"
  exit 1
fi

HOST="$1"
DURATION="${2:-120}"

ssh "$HOST" "stress-ng --cpu 2 --timeout ${DURATION}s"
echo "CPU stress completed on ${HOST}"

