#!/usr/bin/env bash
# 延时通知工具（事件驱动 Timer API）
# 用法: ./scripts/timer.sh <秒数> "到期后发送的消息"
# 示例: ./scripts/timer.sh 60 "主人，1分钟到了"
#       ./scripts/timer.sh 600 "该开会了"
set -uo pipefail

TIMER_API="http://localhost:${TIMER_API_PORT:-8789}"

DELAY="${1:-}"
MESSAGE="${2:-}"

if [ -z "$DELAY" ] || [ -z "$MESSAGE" ]; then
  echo "用法: $0 <秒数> \"消息内容\"" >&2
  echo "示例: $0 60 \"1分钟到了\"" >&2
  exit 1
fi

RESPONSE=$(curl -s -X POST "$TIMER_API/api/timer" \
  -H "Content-Type: application/json" \
  -d "{\"delay_seconds\": $DELAY, \"message\": \"$MESSAGE\"}" 2>/dev/null)

if echo "$RESPONSE" | grep -q '"ok": true'; then
  TIMER_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['timer_id'])" 2>/dev/null || echo "unknown")
  echo "ok: timer_id=$TIMER_ID, fires in ${DELAY}s"
else
  echo "error: $RESPONSE" >&2
  exit 1
fi
