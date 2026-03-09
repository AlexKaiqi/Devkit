#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"
if [ -f "$ENV_FILE" ]; then
  set -a; source "$ENV_FILE"; set +a
fi

HOST="${1:-localhost}"
STT_PORT="${STT_PROXY_PORT:-8787}"
VOICE_PORT="${VOICE_CHAT_PORT:-3001}"

PASS=0; FAIL=0
check() {
  if [ "$1" = "ok" ]; then PASS=$((PASS+1)); echo "   [✓] $2"
  else FAIL=$((FAIL+1)); echo "   [✗] $2"; fi
}

echo "============================================"
echo "  Devkit 验证 ($HOST)"
echo "============================================"
echo ""

echo "── 1. 豆包 STT 代理 (:$STT_PORT) ──"
H=$(curl -sf "http://$HOST:$STT_PORT/health" 2>/dev/null || echo "")
[ -n "$H" ] && check ok "Health: $H" || check fail "Health 不可达"

echo ""
echo "── 2. 风铃 (:$VOICE_PORT) ──"
VC=$(curl -sf -o /dev/null -w "%{http_code}" "http://$HOST:$VOICE_PORT/" 2>/dev/null || echo "000")
[ "$VC" = "200" ] && check ok "HTTP $VC" || check fail "HTTP $VC"

echo ""
echo "── 3. LLM ──"
LLM=$(curl -s -X POST "${LLM_BASE_URL:-https://api.openai.com/v1}/chat/completions" \
  -H "Authorization: Bearer ${LLM_API_KEY:-}" \
  -H "Content-Type: application/json" \
  -d '{"model":"'"${AGENT_MODEL:-gemini-3.1-pro-preview}"'","messages":[{"role":"user","content":"回复OK"}],"max_tokens":10}' 2>/dev/null || echo "")
LT=$(echo "$LLM" | python3 -c "import sys,json; print(json.load(sys.stdin)['choices'][0]['message']['content'])" 2>/dev/null || echo "")
[ -n "$LT" ] && check ok "LLM: \"$LT\"" || check fail "LLM 无响应"

echo ""
echo "============================================"
echo "  通过: $PASS  失败: $FAIL"
echo "============================================"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
