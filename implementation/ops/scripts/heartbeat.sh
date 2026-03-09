#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
NOTIFY="$SCRIPT_DIR/notify.sh"
STATE_DIR="$REPO_ROOT/.heartbeat"
mkdir -p "$STATE_DIR"
cd "$REPO_ROOT"

if [ -f "$REPO_ROOT/.env" ]; then
  set -a; source "$REPO_ROOT/.env"; set +a
fi

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
  exit 0
fi

ALERTS=""
add_alert() {
  local level="$1" msg="$2"
  [ -n "$ALERTS" ] && ALERTS="$ALERTS
"
  ALERTS="${ALERTS}${level} ${msg}"
}

if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
  docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^searxng$' || add_alert "⚠️" "SearXNG 未运行"
fi

for port_name in "8787:STT代理" "8789:Timer API" "3001:风铃"; do
  port="${port_name%%:*}"
  name="${port_name#*:}"
  lsof -i ":$port" &>/dev/null || add_alert "⚠️" "$name (:$port) 未运行"
done

DIRTY_COUNT=$(git status --short 2>/dev/null | wc -l | tr -d ' ')
[ "$DIRTY_COUNT" -gt 20 ] && add_alert "📁" "有 $DIRTY_COUNT 个未提交变更"

STATUS_PATH="$REPO_ROOT/implementation/STATUS.md"
if [ -f "$STATUS_PATH" ]; then
  LAST_MOD=$(stat -f %m "$STATUS_PATH" 2>/dev/null || stat -c %Y "$STATUS_PATH" 2>/dev/null)
  NOW=$(date +%s)
  AGE=$(( (NOW - LAST_MOD) / 3600 ))
  if [ "$AGE" -gt 48 ]; then
    PENDING=$(grep -c '进行中\|pending\|in.progress\|in_progress' "$STATUS_PATH" 2>/dev/null || echo 0)
    [ "$PENDING" -gt 0 ] && add_alert "📋" "implementation/STATUS.md ${AGE}h 未更新，有进行中的任务"
  fi
fi

if [ -n "$ALERTS" ]; then
  HEADER="🌿 *风铃巡检报告*"
  FULL_MSG="$HEADER
$(date '+%Y-%m-%d %H:%M')

$(echo -e "$ALERTS")"
  echo -e "$ALERTS" | grep -q '⚠️' && "$NOTIFY" --urgent "$(echo -e "$FULL_MSG")" || "$NOTIFY" "$(echo -e "$FULL_MSG")"
fi
