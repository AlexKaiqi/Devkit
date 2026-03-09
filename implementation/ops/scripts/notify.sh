#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

if [ -f "$REPO_ROOT/.env" ]; then
  set -a; source "$REPO_ROOT/.env"; set +a
fi

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
  echo "error: TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID 未设置" >&2
  exit 1
fi

URGENT=false
if [ "${1:-}" = "--urgent" ]; then
  URGENT=true
  shift
fi

MESSAGE="${1:-}"
[ -z "$MESSAGE" ] && { echo "用法: $0 [--urgent] "消息内容"" >&2; exit 1; }

HOUR=$(date +%H)
if ! $URGENT && { [ "$HOUR" -ge 23 ] || [ "$HOUR" -lt 8 ]; }; then
  echo "静默时间 (23:00-08:00)，非紧急消息已跳过" >&2
  exit 0
fi

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" -d chat_id="$TELEGRAM_CHAT_ID" -d text="$MESSAGE" -d parse_mode=Markdown 2>/dev/null)
[ "$HTTP_CODE" = "200" ] && echo "ok" || { echo "error: HTTP $HTTP_CODE" >&2; exit 1; }
