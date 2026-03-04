#!/usr/bin/env bash
# Telegram 通知工具
# 用法: ./scripts/notify.sh "消息内容"
#       ./scripts/notify.sh --urgent "紧急消息（静默时间也推送）"
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEVKIT_DIR="$(dirname "$SCRIPT_DIR")"

if [ -f "$DEVKIT_DIR/.env" ]; then
  set -a; source "$DEVKIT_DIR/.env"; set +a
fi

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
  echo "error: TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID 未设置" >&2
  echo "  在 .env 中配置，或通过 @BotFather 创建 Bot" >&2
  exit 1
fi

URGENT=false
if [ "${1:-}" = "--urgent" ]; then
  URGENT=true
  shift
fi

MESSAGE="${1:-}"
if [ -z "$MESSAGE" ]; then
  echo "用法: $0 [--urgent] \"消息内容\"" >&2
  exit 1
fi

HOUR=$(date +%H)
if ! $URGENT && { [ "$HOUR" -ge 23 ] || [ "$HOUR" -lt 8 ]; }; then
  echo "静默时间 (23:00-08:00)，非紧急消息已跳过" >&2
  exit 0
fi

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d chat_id="$TELEGRAM_CHAT_ID" \
  -d text="$MESSAGE" \
  -d parse_mode=Markdown 2>/dev/null)

if [ "$HTTP_CODE" = "200" ]; then
  echo "ok"
else
  echo "error: HTTP $HTTP_CODE" >&2
  exit 1
fi
