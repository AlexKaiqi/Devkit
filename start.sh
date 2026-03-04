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

GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
STT_PORT="${STT_PROXY_PORT:-8787}"
CAMI_PORT="${OPENCAMI_PORT:-3000}"
GATEWAY_TOKEN="${OPENCLAW_GATEWAY_TOKEN:-}"

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

# ── 1. 豆包 STT 代理 ────────────────────────

echo ""
echo "=== 启动服务 ==="
echo ""

if is_port_in_use "$STT_PORT"; then
  echo "  ✓ 豆包 STT 代理已在运行 (:$STT_PORT)"
else
  echo "  启动豆包 STT 代理..."
  nohup "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/services/doubao-stt-proxy/server.py" \
    > /tmp/doubao-stt-proxy.log 2>&1 &
  wait_for_port "$STT_PORT" "豆包 STT 代理" 10
fi

# ── 2. OpenClaw Gateway ──────────────────────

if is_port_in_use "$GATEWAY_PORT"; then
  echo "  ✓ OpenClaw Gateway 已在运行 (:$GATEWAY_PORT)"
else
  echo "  启动 OpenClaw Gateway..."
  nohup openclaw gateway > /tmp/openclaw-gateway.log 2>&1 &
  wait_for_port "$GATEWAY_PORT" "OpenClaw Gateway" 15
fi

# ── 3. OpenCami ──────────────────────────────

if is_port_in_use "$CAMI_PORT"; then
  echo "  ✓ OpenCami 已在运行 (:$CAMI_PORT)"
else
  echo "  启动 OpenCami..."
  CLAWDBOT_GATEWAY_TOKEN="$GATEWAY_TOKEN" \
  STT_BASE_URL="http://localhost:$STT_PORT/v1" \
  OPENAI_API_KEY=doubao-stt-proxy \
  nohup npx opencami \
    --host 0.0.0.0 \
    --port "$CAMI_PORT" \
    --gateway "ws://127.0.0.1:$GATEWAY_PORT" \
    --origin "http://localhost:$CAMI_PORT" \
    --no-open \
    > /tmp/opencami.log 2>&1 &
  wait_for_port "$CAMI_PORT" "OpenCami" 10
fi

# ── 4. Cloudflare Tunnel ─────────────────────

TUNNEL_LOG="/tmp/cloudflared.log"

if pgrep -f "cloudflared.*tunnel" &>/dev/null; then
  echo "  ✓ Cloudflare Tunnel 已在运行"
else
  if command -v cloudflared &>/dev/null; then
    echo "  启动 Cloudflare Tunnel..."
    nohup cloudflared tunnel --url "http://localhost:$CAMI_PORT" --no-autoupdate \
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
echo "  豆包 STT:  http://localhost:$STT_PORT/health"
echo "  Gateway:   ws://localhost:$GATEWAY_PORT"
echo "  OpenCami:  http://localhost:$CAMI_PORT"
if [ -n "$LAN_IP" ]; then
  echo "  局域网:    http://$LAN_IP:$CAMI_PORT"
fi
if [ -n "${TUNNEL_URL:-}" ]; then
  echo ""
  echo "  📱 移动端:  $TUNNEL_URL"
  echo "             (HTTPS, 跨网络, 支持语音)"
fi
echo ""
echo "  日志:"
echo "    tail -f /tmp/doubao-stt-proxy.log"
echo "    tail -f /tmp/openclaw-gateway.log"
echo "    tail -f /tmp/opencami.log"
echo "    tail -f /tmp/cloudflared.log"
echo ""
echo "  停止: ./stop.sh"
echo ""
