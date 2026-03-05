#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "$SCRIPT_DIR/.env" ] && { set -a; source "$SCRIPT_DIR/.env" 2>/dev/null; set +a; }

echo "停止服务..."

OPENCAMI_PORT="${OPENCAMI_PORT:-3000}"
VOICE_CHAT_PORT="${VOICE_CHAT_PORT:-3001}"
OPENCLAW_GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
STT_PROXY_PORT="${STT_PROXY_PORT:-8787}"

for port in $OPENCAMI_PORT $VOICE_CHAT_PORT $OPENCLAW_GATEWAY_PORT $STT_PROXY_PORT; do
  pids=$(lsof -t -i ":$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "$pids" | xargs kill -9 2>/dev/null || true
    echo "  ✓ 已停止 :$port"
  fi
done

tg_pids=$(pgrep -f "telegram-bot/bot.py" 2>/dev/null || true)
if [ -n "$tg_pids" ]; then
  echo "$tg_pids" | xargs kill 2>/dev/null || true
  echo "  ✓ 已停止 Telegram Bot"
fi

cf_pids=$(pgrep -f "cloudflared.*tunnel" 2>/dev/null || true)
if [ -n "$cf_pids" ]; then
  echo "$cf_pids" | xargs kill 2>/dev/null || true
  echo "  ✓ 已停止 cloudflared"
fi

if command -v docker &>/dev/null && docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^searxng$'; then
  docker compose -f "$SCRIPT_DIR/docker-compose.yml" stop searxng > /dev/null 2>&1
  echo "  ✓ 已停止 SearXNG"
fi

echo "done"
