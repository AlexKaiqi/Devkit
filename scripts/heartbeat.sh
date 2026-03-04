#!/usr/bin/env bash
# 定期巡检脚本 — 由 launchd 每 30 分钟调用
# 检查服务、邮件、项目状态，异常时通过 Telegram 通知
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEVKIT_DIR="$(dirname "$SCRIPT_DIR")"
NOTIFY="$SCRIPT_DIR/notify.sh"
STATE_DIR="$DEVKIT_DIR/.heartbeat"
mkdir -p "$STATE_DIR"

cd "$DEVKIT_DIR"

if [ -f "$DEVKIT_DIR/.env" ]; then
  set -a; source "$DEVKIT_DIR/.env"; set +a
fi

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
  exit 0
fi

ALERTS=""

add_alert() {
  local level="$1" msg="$2"
  if [ -n "$ALERTS" ]; then
    ALERTS="$ALERTS\n"
  fi
  ALERTS="${ALERTS}${level} ${msg}"
}

# ── 1. 服务健康 ──────────────────────────────

if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
  if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^searxng$'; then
    add_alert "⚠️" "SearXNG 未运行"
  fi
fi

for port_name in "8787:STT代理" "18789:Gateway" "3000:OpenCami" "3001:语音对话"; do
  port="${port_name%%:*}"
  name="${port_name#*:}"
  if ! lsof -i ":$port" &>/dev/null; then
    add_alert "⚠️" "$name (:$port) 未运行"
  fi
done

# ── 2. Cursor 任务 ───────────────────────────

CURSOR_PIDS=$(pgrep -f "cursor agent" 2>/dev/null || true)
if [ -n "$CURSOR_PIDS" ]; then
  for pid in $CURSOR_PIDS; do
    ELAPSED=$(ps -o etime= -p "$pid" 2>/dev/null | tr -d ' ')
    if echo "$ELAPSED" | grep -qE '^[0-9]+-|^[0-9]{2}:[0-9]{2}:[0-9]{2}'; then
      add_alert "⏳" "Cursor Agent (PID $pid) 运行已久: $ELAPSED"
    fi
  done
fi

# ── 3. 新邮件 ────────────────────────────────

if command -v himalaya &>/dev/null; then
  LAST_CHECK="$STATE_DIR/last_mail_check"
  NEW_MAIL=$(himalaya envelope list --page-size 3 2>/dev/null | head -5 || true)
  MAIL_HASH=$(echo "$NEW_MAIL" | md5 2>/dev/null || echo "$NEW_MAIL" | md5sum 2>/dev/null | cut -d' ' -f1)

  if [ -f "$LAST_CHECK" ]; then
    OLD_HASH=$(cat "$LAST_CHECK")
    if [ "$MAIL_HASH" != "$OLD_HASH" ] && [ -n "$NEW_MAIL" ]; then
      add_alert "📬" "新邮件:\n$NEW_MAIL"
    fi
  fi
  echo "$MAIL_HASH" > "$LAST_CHECK"
fi

# ── 4. Git 状态 ──────────────────────────────

DIRTY_COUNT=$(git status --short 2>/dev/null | wc -l | tr -d ' ')
if [ "$DIRTY_COUNT" -gt 20 ]; then
  add_alert "📁" "有 $DIRTY_COUNT 个未提交变更"
fi

# ── 5. STATUS.md 过期检查 ────────────────────

if [ -f "$DEVKIT_DIR/STATUS.md" ]; then
  LAST_MOD=$(stat -f %m "$DEVKIT_DIR/STATUS.md" 2>/dev/null || stat -c %Y "$DEVKIT_DIR/STATUS.md" 2>/dev/null)
  NOW=$(date +%s)
  AGE=$(( (NOW - LAST_MOD) / 3600 ))
  if [ "$AGE" -gt 48 ]; then
    PENDING=$(grep -c '进行中\|pending\|in.progress' "$DEVKIT_DIR/STATUS.md" 2>/dev/null || echo 0)
    if [ "$PENDING" -gt 0 ]; then
      add_alert "📋" "STATUS.md ${AGE}h 未更新，有进行中的任务"
    fi
  fi
fi

# ── 6. 发送通知 ──────────────────────────────

if [ -n "$ALERTS" ]; then
  HAS_URGENT=false
  echo -e "$ALERTS" | grep -q '⚠️' && HAS_URGENT=true

  HEADER="🌿 *希露菲巡检报告*"
  FULL_MSG="$HEADER\n$(date '+%Y-%m-%d %H:%M')\n\n$(echo -e "$ALERTS")"

  if $HAS_URGENT; then
    "$NOTIFY" --urgent "$(echo -e "$FULL_MSG")"
  else
    "$NOTIFY" "$(echo -e "$FULL_MSG")"
  fi
fi
