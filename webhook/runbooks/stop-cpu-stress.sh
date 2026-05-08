#!/usr/bin/env bash
set -euo pipefail

INSTANCE="${1:-}"
DRILL_HOST="${GUARDIAN_DRILL_HOST:-}"
DRILL_SSH_USER="${GUARDIAN_DRILL_SSH_USER:-guardian}"
SSH_KEY_PATH="${GUARDIAN_DRILL_SSH_KEY_PATH:-/root/.ssh/guardian_deploy_ed25519}"

if [[ -z "${INSTANCE}" ]]; then
  echo "missing alert instance" >&2
  exit 2
fi

if [[ -z "${DRILL_HOST}" ]]; then
  echo "GUARDIAN_DRILL_HOST is not configured" >&2
  exit 2
fi

TARGET_HOST="${INSTANCE%%:*}"

if [[ "${TARGET_HOST}" != "${DRILL_HOST}" ]]; then
  echo "refusing remediation for non-drill host ${TARGET_HOST}" >&2
  exit 3
fi

if [[ ! -f "${SSH_KEY_PATH}" ]]; then
  echo "SSH key not found at ${SSH_KEY_PATH}" >&2
  exit 4
fi

SSH_OPTS=(
  -i "${SSH_KEY_PATH}"
  -o BatchMode=yes
  -o IdentitiesOnly=yes
  -o StrictHostKeyChecking=accept-new
)

REMOTE_COMMAND=$'if sudo pgrep -x stress-ng >/dev/null; then\n  sudo pkill -INT -x stress-ng || true\n  sudo pkill -INT -f "^stress-ng-cpu" || true\n  echo "Stopped stress-ng on drill host."\nelse\n  echo "No stress-ng process found."\nfi'

echo "Executing drill remediation on ${DRILL_SSH_USER}@${DRILL_HOST}"
ssh "${SSH_OPTS[@]}" "${DRILL_SSH_USER}@${DRILL_HOST}" "${REMOTE_COMMAND}"
