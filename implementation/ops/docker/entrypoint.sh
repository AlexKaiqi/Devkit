#!/usr/bin/env bash
set -euo pipefail

echo "======================================="
echo "  Devkit Docker — 初始化"
echo "======================================="

for var in DOUBAO_APPID DOUBAO_TOKEN LLM_API_KEY LLM_BASE_URL; do
  if [ -z "${!var:-}" ]; then
    echo "error: $var 未设置"
    exit 1
  fi
done

echo "[✓] 环境变量已加载"

echo ""
echo "======================================="
echo "  启动服务..."
echo "======================================="

STT_PORT="${STT_PROXY_PORT:-8787}"
VOICE_PORT="${VOICE_CHAT_PORT:-3001}"

python /app/implementation/services/speech/server.py &
echo "[✓] STT Proxy 启动中 (:$STT_PORT)"

STT_PROXY_URL="http://localhost:$STT_PORT" WORKSPACE_DIR="${WORKSPACE_DIR:-implementation/assets/persona}" DEVKIT_DIR=/app python /app/implementation/channels/fengling/server.py &
echo "[✓] 风铃启动中 (:$VOICE_PORT)"

if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
  STT_PROXY_URL="http://localhost:$STT_PORT"   WORKSPACE_DIR="${WORKSPACE_DIR:-implementation/assets/persona}"   DEVKIT_DIR=/app   python /app/implementation/channels/telegram/bot.py &
  echo "[✓] Telegram Bot 启动中"
fi

if command -v cloudflared &>/dev/null; then
  cloudflared tunnel --url "http://localhost:$VOICE_PORT" --protocol http2 --no-autoupdate > /tmp/cloudflared.log 2>&1 &
  echo "[✓] Cloudflare Tunnel 启动中"
fi

echo ""
echo "======================================="
echo "  服务已启动"
echo "  风铃: http://localhost:$VOICE_PORT"
echo "  Agent: model=${AGENT_MODEL:-gemini-3.1-pro-preview}"
echo "======================================="

wait
