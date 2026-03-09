#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── 加载 .env ────────────────────────────────

if [ ! -f "$SCRIPT_DIR/.env" ]; then
  echo "error: .env 不存在，先运行 ./setup.sh"
  exit 1
fi
set -a; source "$SCRIPT_DIR/.env"; set +a

STT_PORT="${STT_PROXY_PORT:-8787}"
TIMER_API_PORT="${TIMER_API_PORT:-8789}"

# ── 辅助函数 ─────────────────────────────────

is_port_in_use() { lsof -i ":$1" &>/dev/null; }

wait_for_port() {
  local port=$1 name=$2 max=$3
  for i in $(seq 1 "$max"); do
    if is_port_in_use "$port"; then echo "  ✓ $name (:$port)"; return 0; fi
    sleep 1
  done
  echo "  ✗ $name 启动超时"; return 1
}

# ── 0. SearXNG 搜索引擎 (Docker Compose) ─────

echo ""
echo "=== 启动服务 ==="
echo ""

SEARXNG_PORT=8080
if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
  if docker ps --format '{{.Names}}' | grep -q '^searxng$'; then
    echo "  ✓ SearXNG 已在运行 (:$SEARXNG_PORT)"
  else
    echo "  启动 SearXNG..."
    docker compose -f "$SCRIPT_DIR/docker-compose.yml" up -d searxng > /dev/null 2>&1
    sleep 3
    if docker ps --format '{{.Names}}' | grep -q '^searxng$'; then
      echo "  ✓ SearXNG (:$SEARXNG_PORT)"
    else
      echo "  ✗ SearXNG 启动失败"
    fi
  fi
else
  echo "  - Docker 未安装或未运行，跳过 SearXNG"
fi

# ── 1. 豆包 STT 代理 ────────────────────────

if is_port_in_use "$STT_PORT"; then
  echo "  ✓ 豆包 STT 代理已在运行 (:$STT_PORT)"
else
  echo "  启动豆包 STT 代理..."
  nohup "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/services/doubao-stt-proxy/server.py" \
    > /tmp/doubao-stt-proxy.log 2>&1 &
  wait_for_port "$STT_PORT" "豆包 STT 代理" 10
fi

# ── 2. 风铃 (Voice Chat) ─────────────────────

VOICE_PORT="${VOICE_CHAT_PORT:-3001}"

if is_port_in_use "$VOICE_PORT"; then
  echo "  ✓ 风铃已在运行 (:$VOICE_PORT)"
else
  echo "  启动风铃..."
  STT_PROXY_URL="http://localhost:$STT_PORT" \
  DOUBAO_APPID="$DOUBAO_APPID" \
  DOUBAO_TOKEN="$DOUBAO_TOKEN" \
  LLM_API_KEY="$LLM_API_KEY" \
  LLM_BASE_URL="$LLM_BASE_URL" \
  AGENT_MODEL="${AGENT_MODEL:-gemini-3.1-pro-preview}" \
  WORKSPACE_DIR="${WORKSPACE_DIR:-persona}" \
  DEVKIT_DIR="$SCRIPT_DIR" \
  VOICE_CHAT_PORT="$VOICE_PORT" \
  nohup "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/services/voice-chat/server.py" \
    > /tmp/voice-chat.log 2>&1 &
  wait_for_port "$VOICE_PORT" "风铃" 10
fi

# ── 5. Telegram Bot ──────────────────────────

if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
  if pgrep -f "telegram-bot/bot.py" &>/dev/null; then
    echo "  ✓ Telegram Bot 已在运行"
  else
    echo "  启动 Telegram Bot..."
    STT_PROXY_URL="http://localhost:$STT_PORT" \
    DOUBAO_APPID="$DOUBAO_APPID" \
    DOUBAO_TOKEN="$DOUBAO_TOKEN" \
    LLM_API_KEY="$LLM_API_KEY" \
    LLM_BASE_URL="$LLM_BASE_URL" \
    AGENT_MODEL="${AGENT_MODEL:-gemini-3.1-pro-preview}" \
    WORKSPACE_DIR="${WORKSPACE_DIR:-persona}" \
    DEVKIT_DIR="$SCRIPT_DIR" \
    TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
    TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}" \
    TIMER_API_PORT="$TIMER_API_PORT" \
    nohup "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/services/telegram-bot/bot.py" \
      > /tmp/telegram-bot.log 2>&1 &
    sleep 2
    if pgrep -f "telegram-bot/bot.py" &>/dev/null; then
      echo "  ✓ Telegram Bot"
    else
      echo "  ✗ Telegram Bot 启动失败，查看 /tmp/telegram-bot.log"
    fi
  fi
else
  echo "  - Telegram Bot 未配置（TELEGRAM_BOT_TOKEN 为空）"
fi

# ── 6. Cloudflare Tunnel ─────────────────────

TUNNEL_LOG="/tmp/cloudflared.log"

if pgrep -f "cloudflared.*tunnel" &>/dev/null; then
  echo "  ✓ Cloudflare Tunnel 已在运行"
else
  if command -v cloudflared &>/dev/null; then
    echo "  启动 Cloudflare Tunnel..."
    nohup cloudflared tunnel --url "http://localhost:$VOICE_PORT" --no-autoupdate \
      > "$TUNNEL_LOG" 2>&1 &
    sleep 5
    TUNNEL_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | tail -1)
    if [ -n "$TUNNEL_URL" ]; then
      echo "  ✓ Cloudflare Tunnel"
    else
      echo "  ! Tunnel 启动中，稍后查看 $TUNNEL_LOG"
    fi
  else
    echo "  - cloudflared 未安装，跳过 Tunnel（brew install cloudflared）"
  fi
fi

# ── 状态 ─────────────────────────────────────

LAN_IP=$(ifconfig 2>/dev/null | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)
TUNNEL_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | tail -1)

echo ""
echo "=== 所有服务已启动 ==="
echo ""
echo "  SearXNG:   http://localhost:$SEARXNG_PORT"
echo "  豆包 STT:  http://localhost:$STT_PORT/health"
echo "  🎐 风铃:   http://localhost:$VOICE_PORT"
echo "  Timer API: http://localhost:$TIMER_API_PORT/health"
echo "  Agent:     model=${AGENT_MODEL:-gemini-3.1-pro-preview}"
if [ -n "$LAN_IP" ]; then
  echo "  局域网:    http://$LAN_IP:$VOICE_PORT"
fi
if [ -n "${TUNNEL_URL:-}" ]; then
  echo ""
  echo "  📱 移动端:  $TUNNEL_URL"
  echo "             (HTTPS, 跨网络, 支持语音)"
fi
echo ""
echo "  日志:"
echo "    tail -f /tmp/doubao-stt-proxy.log"
echo "    tail -f /tmp/voice-chat.log"
echo "    tail -f /tmp/telegram-bot.log"
echo "    tail -f /tmp/cloudflared.log"
echo ""
echo "  停止: ./stop.sh"
echo ""
