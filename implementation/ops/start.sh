#!/usr/bin/env bash
set -euo pipefail

OPS_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$OPS_DIR/../.." && pwd)"
cd "$REPO_ROOT"

if [ ! -f "$REPO_ROOT/.env" ]; then
  echo "error: .env 不存在，先运行 ./setup.sh"
  exit 1
fi
set -a; source "$REPO_ROOT/.env"; set +a

PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
WORKSPACE_DIR_VALUE="${WORKSPACE_DIR:-implementation/assets/persona}"
STT_PORT="${STT_PROXY_PORT:-8787}"
VOICE_PORT="${VOICE_CHAT_PORT:-3001}"
TIMER_API_PORT="${TIMER_API_PORT:-8789}"
SEARXNG_PORT=8080
NEO4J_BOLT_PORT="${NEO4J_BOLT_PORT:-7687}"
NEO4J_HTTP_PORT="${NEO4J_HTTP_PORT:-7474}"

is_port_in_use() { lsof -i ":$1" &>/dev/null; }

wait_for_port() {
  local port=$1 name=$2 max=$3
  for _ in $(seq 1 "$max"); do
    if is_port_in_use "$port"; then
      echo "  ✓ $name (:$port)"
      return 0
    fi
    sleep 1
  done
  echo "  ✗ $name 启动超时"
  return 1
}

echo ""
echo "=== 启动服务 ==="
echo ""

if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
  if docker ps --format '{{.Names}}' | grep -q '^searxng$'; then
    echo "  ✓ SearXNG 已在运行 (:$SEARXNG_PORT)"
  else
    echo "  启动 SearXNG..."
    docker compose -f "$REPO_ROOT/docker-compose.yml" up -d searxng > /dev/null 2>&1
    # 等待 HTTP 可达，而非仅检查容器存在
    for i in $(seq 1 10); do
      if curl -s -o /dev/null --max-time 2 "http://localhost:$SEARXNG_PORT/healthz" 2>/dev/null; then
        echo "  ✓ SearXNG (:$SEARXNG_PORT)"
        break
      fi
      sleep 1
      [ "$i" -eq 10 ] && echo "  ⚠ SearXNG 容器已启动但 HTTP 未就绪，稍后可用 ./check.sh 确认"
    done
  fi
else
  echo "  - Docker 未安装或未运行，跳过 SearXNG"
fi

if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
  if docker ps --format '{{.Names}}' | grep -q '^devkit-neo4j$'; then
    echo "  ✓ Neo4j 已在运行 (:$NEO4J_BOLT_PORT)"
  else
    echo "  启动 Neo4j..."
    docker compose -f "$REPO_ROOT/implementation/services/neo4j/docker-compose.yml" up -d > /dev/null 2>&1
    sleep 5
    docker ps --format '{{.Names}}' | grep -q '^devkit-neo4j$' && echo "  ✓ Neo4j (:$NEO4J_BOLT_PORT)" || echo "  ✗ Neo4j 启动失败"
  fi
else
  echo "  - Docker 未安装或未运行，跳过 Neo4j"
fi

PROXY_PORT="${CLAUDE_CODE_PROXY_PORT:-9999}"
if is_port_in_use "$PROXY_PORT"; then
  echo "  ✓ Claude Code Proxy 已在运行 (:$PROXY_PORT)"
else
  echo "  启动 Claude Code Proxy..."
  CLAUDE_CODE_PROXY_PORT="$PROXY_PORT" \
  LLM_API_KEY="$LLM_API_KEY" \
  nohup "$PYTHON_BIN" "$REPO_ROOT/implementation/services/openrouter-proxy/proxy.py" > /tmp/claude-proxy.log 2>&1 &
  wait_for_port "$PROXY_PORT" "Claude Code Proxy" 5
fi

if is_port_in_use "$STT_PORT"; then
  echo "  ✓ 豆包 STT 代理已在运行 (:$STT_PORT)"
else
  echo "  启动豆包 STT 代理..."
  nohup "$PYTHON_BIN" "$REPO_ROOT/implementation/services/speech/server.py" > /tmp/doubao-stt-proxy.log 2>&1 &
  wait_for_port "$STT_PORT" "豆包 STT 代理" 10
fi

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
  WORKSPACE_DIR="$WORKSPACE_DIR_VALUE" \
  DEVKIT_DIR="$REPO_ROOT" \
  VOICE_CHAT_PORT="$VOICE_PORT" \
  CLAUDE_CODE_PROXY_PORT="$PROXY_PORT" \
  NEO4J_URI="bolt://localhost:$NEO4J_BOLT_PORT" \
  NEO4J_PASSWORD="${NEO4J_PASSWORD:-devkit2026}" \
  nohup "$PYTHON_BIN" "$REPO_ROOT/implementation/channels/fengling/server.py" > /tmp/voice-chat.log 2>&1 &
  wait_for_port "$VOICE_PORT" "风铃" 10
fi

if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
  if pgrep -f "implementation/channels/telegram/bot.py" &>/dev/null; then
    echo "  ✓ Telegram Bot 已在运行"
  else
    echo "  启动 Telegram Bot..."
    STT_PROXY_URL="http://localhost:$STT_PORT" \
    DOUBAO_APPID="$DOUBAO_APPID" \
    DOUBAO_TOKEN="$DOUBAO_TOKEN" \
    LLM_API_KEY="$LLM_API_KEY" \
    LLM_BASE_URL="$LLM_BASE_URL" \
    AGENT_MODEL="${AGENT_MODEL:-gemini-3.1-pro-preview}" \
    WORKSPACE_DIR="$WORKSPACE_DIR_VALUE" \
    DEVKIT_DIR="$REPO_ROOT" \
    TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
    TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}" \
    TIMER_API_PORT="$TIMER_API_PORT" \
    nohup "$PYTHON_BIN" "$REPO_ROOT/implementation/channels/telegram/bot.py" > /tmp/telegram-bot.log 2>&1 &
    sleep 2
    pgrep -f "implementation/channels/telegram/bot.py" &>/dev/null && echo "  ✓ Telegram Bot" || echo "  ✗ Telegram Bot 启动失败，查看 /tmp/telegram-bot.log"
  fi
else
  echo "  - Telegram Bot 未配置（TELEGRAM_BOT_TOKEN 为空）"
fi

LAN_IP=$(ifconfig 2>/dev/null | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)

echo ""
echo "=== 所有服务已启动 ==="
echo ""
echo "  Proxy:     http://localhost:$PROXY_PORT (Claude Code)"
echo "  SearXNG:   http://localhost:$SEARXNG_PORT"
echo "  Neo4j:     http://localhost:$NEO4J_HTTP_PORT (bolt://localhost:$NEO4J_BOLT_PORT)"
echo "  豆包 STT:  http://localhost:$STT_PORT/health"
echo "  🎐 风铃:   http://localhost:$VOICE_PORT"
echo "  Timer API: http://localhost:$TIMER_API_PORT/health"
echo "  Agent:     model=${AGENT_MODEL:-gemini-3.1-pro-preview}"
[ -n "$LAN_IP" ] && echo "  局域网:    http://$LAN_IP:$VOICE_PORT"
echo ""
echo "  日志:"
echo "    tail -f /tmp/claude-proxy.log"
echo "    tail -f /tmp/doubao-stt-proxy.log"
echo "    tail -f /tmp/voice-chat.log"
echo "    tail -f /tmp/telegram-bot.log"
echo ""
echo "  停止: ./stop.sh"
echo ""
