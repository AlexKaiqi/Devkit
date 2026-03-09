#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV="$PROJECT_DIR/.venv"

if [ ! -d "$VENV" ]; then
  echo "Creating venv..."
  python3 -m venv "$VENV"
fi

"$VENV/bin/pip" install -q -r "$SCRIPT_DIR/requirements.txt"

if [ -z "${DOUBAO_APPID:-}" ] || [ -z "${DOUBAO_TOKEN:-}" ]; then
  echo "error: DOUBAO_APPID and DOUBAO_TOKEN must be set"
  echo "  cp .env.example .env  # then fill in values"
  exit 1
fi

export DOUBAO_APPID
export DOUBAO_TOKEN
export STT_PROXY_PORT="${STT_PROXY_PORT:-8787}"

echo ""
echo "  Doubao STT Proxy"
echo "  http://localhost:$STT_PROXY_PORT"
echo "  Whisper API: POST /v1/audio/transcriptions"
echo ""

exec "$VENV/bin/python" "$SCRIPT_DIR/server.py"
