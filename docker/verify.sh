#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"
if [ -f "$ENV_FILE" ]; then
  set -a; source "$ENV_FILE"; set +a
fi

HOST="${1:-localhost}"
STT_PORT="${STT_PROXY_PORT:-8787}"
GW_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
CAMI_PORT="${OPENCAMI_PORT:-3000}"

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
echo "── 2. OpenClaw Gateway (:$GW_PORT) ──"
GC=$(curl -sf -o /dev/null -w "%{http_code}" "http://$HOST:$GW_PORT/" 2>/dev/null || echo "000")
[ "$GC" = "200" ] && check ok "HTTP $GC" || check fail "HTTP $GC"

echo ""
echo "── 3. OpenCami (:$CAMI_PORT) ──"
CC=$(curl -sf -o /dev/null -w "%{http_code}" "http://$HOST:$CAMI_PORT/" 2>/dev/null || echo "000")
[ "$CC" = "200" ] && check ok "HTTP $CC" || check fail "HTTP $CC"

P=$(curl -s "http://$HOST:$CAMI_PORT/api/ping" 2>/dev/null || echo '{}')
POK=$(echo "$P" | python3 -c "import sys,json; print(json.load(sys.stdin).get('ok',False))" 2>/dev/null)
[ "$POK" = "True" ] && check ok "Gateway 已配对" || check fail "Gateway: $P"

echo ""
echo "── 4. LLM ──"
LLM=$(curl -s -X POST "${LLM_BASE_URL:-https://api.openai.com/v1}/chat/completions" \
  -H "Authorization: Bearer ${LLM_API_KEY:-}" \
  -H "Content-Type: application/json" \
  -d '{"model":"'"${LLM_MODEL:-gpt-4o}"'","messages":[{"role":"user","content":"回复OK"}],"max_tokens":10}' 2>/dev/null || echo "")
LT=$(echo "$LLM" | python3 -c "import sys,json; print(json.load(sys.stdin)['choices'][0]['message']['content'])" 2>/dev/null || echo "")
[ -n "$LT" ] && check ok "LLM: \"$LT\"" || check fail "LLM 无响应"

echo ""
echo "============================================"
echo "  通过: $PASS  失败: $FAIL"
echo "============================================"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
