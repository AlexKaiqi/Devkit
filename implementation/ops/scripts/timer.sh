#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
TIMER_API="http://localhost:${TIMER_API_PORT:-8789}"
PYTHON_BIN="$REPO_ROOT/.venv/bin/python"

DELAY="${1:-}"
MESSAGE="${2:-}"

if [ -z "$DELAY" ] || [ -z "$MESSAGE" ]; then
  echo "用法: $0 <秒数> "消息内容"" >&2
  exit 1
fi

RESPONSE=$(curl -s -X POST "$TIMER_API/api/timer" -H "Content-Type: application/json" -d "{"delay_seconds": $DELAY, "message": "$MESSAGE"}" 2>/dev/null)

if echo "$RESPONSE" | grep -q '"ok": true'; then
  TIMER_ID=$(echo "$RESPONSE" | "$PYTHON_BIN" -c "import sys,json; print(json.load(sys.stdin)['timer_id'])" 2>/dev/null || echo "unknown")
  echo "ok: timer_id=$TIMER_ID, fires in ${DELAY}s"
else
  echo "error: $RESPONSE" >&2
  exit 1
fi
