#!/usr/bin/env bash
set -euo pipefail

MEDIA_PATH="$1"
PORT="${STT_PROXY_PORT:-8787}"

result=$(curl -sf -F "file=@${MEDIA_PATH}" -F "model=whisper-1" -F "language=zh" \
  "http://localhost:${PORT}/v1/audio/transcriptions" 2>/dev/null)

echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('text',''))"
