#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <ssh-host> [duration-seconds]"
  exit 1
fi

HOST="$1"
DURATION="${2:-120}"

# Saturate all visible CPUs so the instance-level average reliably breaches the alert threshold.
ssh "$HOST" "stress-ng --cpu 0 --timeout ${DURATION}s"
echo "CPU stress completed on ${HOST}"
