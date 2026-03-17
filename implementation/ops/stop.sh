#!/usr/bin/env bash
set -euo pipefail

OPS_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$OPS_DIR/../.." && pwd)"
[ -f "$REPO_ROOT/.env" ] && { set -a; source "$REPO_ROOT/.env" 2>/dev/null; set +a; }

echo "停止服务..."

VOICE_CHAT_PORT="${VOICE_CHAT_PORT:-3001}"
STT_PROXY_PORT="${STT_PROXY_PORT:-8787}"
TIMER_API_PORT="${TIMER_API_PORT:-8789}"
CLAUDE_CODE_PROXY_PORT="${CLAUDE_CODE_PROXY_PORT:-9999}"

for port in "$VOICE_CHAT_PORT" "$STT_PROXY_PORT" "$TIMER_API_PORT" "$CLAUDE_CODE_PROXY_PORT"; do
  pids=$(lsof -t -i ":$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "$pids" | xargs kill -9 2>/dev/null || true
    echo "  ✓ 已停止 :$port"
  fi
done

tg_pids=$(pgrep -f "implementation/channels/telegram/bot.py" 2>/dev/null || true)
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
  docker compose -f "$REPO_ROOT/docker-compose.yml" stop searxng > /dev/null 2>&1
  echo "  ✓ 已停止 SearXNG"
fi

if command -v docker &>/dev/null && docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^devkit-neo4j$'; then
  docker compose -f "$REPO_ROOT/implementation/services/neo4j/docker-compose.yml" stop > /dev/null 2>&1
  echo "  ✓ 已停止 Neo4j"
fi

echo "done"
