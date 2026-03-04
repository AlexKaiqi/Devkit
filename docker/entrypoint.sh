#!/usr/bin/env bash
set -euo pipefail

OPENCLAW_HOME="${OPENCLAW_HOME:-/root/.openclaw}"

echo "======================================="
echo "  Devkit Docker — 初始化"
echo "======================================="

# ── 1. 环境变量检查 ──────────────────────────

for var in DOUBAO_APPID DOUBAO_TOKEN LLM_API_KEY LLM_BASE_URL OPENCLAW_GATEWAY_TOKEN; do
  if [ -z "${!var:-}" ]; then
    echo "error: $var 未设置"
    exit 1
  fi
done
echo "[✓] 环境变量已加载"

# ── 2. 生成 OpenClaw 配置 ────────────────────

mkdir -p "$OPENCLAW_HOME/workspace"

cat > "$OPENCLAW_HOME/openclaw.json" <<EOJSON
{
  "meta": { "lastTouchedVersion": "docker" },
  "auth": { "profiles": {} },
  "models": {
    "mode": "merge",
    "providers": {
      "llm": {
        "baseUrl": "${LLM_BASE_URL}",
        "apiKey": "${LLM_API_KEY}",
        "api": "openai-completions",
        "models": [{
          "id": "${LLM_MODEL:-gpt-4o}",
          "name": "LLM",
          "reasoning": false,
          "input": ["text"],
          "contextWindow": 200000,
          "maxTokens": 32000
        }]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": { "primary": "llm/${LLM_MODEL:-gpt-4o}" },
      "models": { "llm/${LLM_MODEL:-gpt-4o}": {} },
      "workspace": "$OPENCLAW_HOME/workspace",
      "compaction": { "mode": "safeguard" },
      "maxConcurrent": 4,
      "subagents": { "maxConcurrent": 8 }
    }
  },
  "tools": {
    "profile": "messaging",
    "media": {
      "audio": {
        "enabled": true,
        "maxBytes": 20971520,
        "models": [{
          "type": "cli",
          "command": "/app/services/doubao-stt-proxy/transcribe.sh",
          "args": ["{{MediaPath}}"],
          "timeoutSeconds": 30,
          "language": "zh"
        }]
      }
    }
  },
  "messages": { "ackReactionScope": "group-mentions" },
  "commands": { "native": "auto", "nativeSkills": "auto", "restart": true, "ownerDisplay": "raw" },
  "session": { "dmScope": "per-channel-peer" },
  "hooks": { "internal": { "enabled": true, "entries": { "session-memory": { "enabled": true } } } },
  "gateway": {
    "port": ${OPENCLAW_GATEWAY_PORT:-18789},
    "mode": "local",
    "bind": "lan",
    "auth": { "mode": "token", "token": "${OPENCLAW_GATEWAY_TOKEN}" },
    "controlUi": {
      "allowInsecureAuth": true,
      "allowedOrigins": [
        "http://localhost:${OPENCAMI_PORT:-3000}",
        "http://127.0.0.1:${OPENCAMI_PORT:-3000}"
      ]
    }
  },
  "skills": { "install": { "nodeManager": "npm" } }
}
EOJSON
echo "[✓] openclaw.json 已生成"

# ── 3. 同步 Agent 配置 ───────────────────────

for f in IDENTITY.md SOUL.md USER.md AGENTS.md TOOLS.md HEARTBEAT.md; do
  if [ -f "/app/openclaw/$f" ]; then
    cp "/app/openclaw/$f" "$OPENCLAW_HOME/workspace/$f"
  fi
done
echo "[✓] Agent 配置已同步"

# ── 4. Patch OpenCami STT (hardcoded URL → env) ─

CAMI_ROUTER=$(find /usr/local/lib/node_modules/opencami -name "router-*.js" -path "*/server/assets/*" 2>/dev/null | head -1)
if [ -n "$CAMI_ROUTER" ] && grep -q 'https://api.openai.com/v1/audio/transcriptions' "$CAMI_ROUTER"; then
  python3 -c "
import sys
f = sys.argv[1]
txt = open(f).read()
old = 'const res = await fetch(\"https://api.openai.com/v1/audio/transcriptions\"'
new = 'const sttBaseUrl = process.env.STT_BASE_URL || \"https://api.openai.com/v1\";\n  const res = await fetch(\`\${sttBaseUrl}/audio/transcriptions\`'
open(f, 'w').write(txt.replace(old, new, 1))
" "$CAMI_ROUTER"
  echo "[✓] OpenCami STT 已 patch"
else
  echo "[…] OpenCami STT patch 跳过"
fi

# ── 5. 启动 supervisor ───────────────────────

cat > /etc/supervisor/conf.d/devkit.conf <<EOCONF
[program:stt-proxy]
command=/app/.venv/bin/python /app/services/doubao-stt-proxy/server.py
environment=DOUBAO_APPID="%(ENV_DOUBAO_APPID)s",DOUBAO_TOKEN="%(ENV_DOUBAO_TOKEN)s",STT_PROXY_PORT="%(ENV_STT_PROXY_PORT)s"
autorestart=true
stdout_logfile=/dev/fd/1
stdout_logfile_maxbytes=0
stderr_logfile=/dev/fd/2
stderr_logfile_maxbytes=0

[program:gateway]
command=openclaw gateway
environment=HOME="/root"
autorestart=true
stdout_logfile=/dev/fd/1
stdout_logfile_maxbytes=0
stderr_logfile=/dev/fd/2
stderr_logfile_maxbytes=0

[program:opencami]
command=npx opencami --host 0.0.0.0 --port %(ENV_OPENCAMI_PORT)s --gateway ws://127.0.0.1:%(ENV_OPENCLAW_GATEWAY_PORT)s --no-open
environment=CLAWDBOT_GATEWAY_TOKEN="%(ENV_OPENCLAW_GATEWAY_TOKEN)s",STT_BASE_URL="http://localhost:%(ENV_STT_PROXY_PORT)s/v1",OPENAI_API_KEY="doubao-stt-proxy",OPENCAMI_ORIGIN="http://localhost:%(ENV_OPENCAMI_PORT)s",HOME="/root"
autorestart=true
startsecs=8
stdout_logfile=/dev/fd/1
stdout_logfile_maxbytes=0
stderr_logfile=/dev/fd/2
stderr_logfile_maxbytes=0
EOCONF

cat > /app/docker/fix-scopes.sh <<'FIXSCOPE'
#!/usr/bin/env bash
sleep 20
for i in $(seq 1 30); do
  DEVICE_ID=$(curl -s http://localhost:3000/api/ping 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('deviceId',''))" 2>/dev/null)
  if [ -n "$DEVICE_ID" ]; then
    openclaw devices rotate \
      --device "$DEVICE_ID" \
      --role operator \
      --scope operator.admin \
      --scope operator.approvals \
      --scope operator.pairing \
      --scope operator.read \
      --scope operator.write >/dev/null 2>&1 && echo "[✓] OpenCami scopes 已修复" && exit 0
  fi
  sleep 5
done
echo "[✗] OpenCami scope 修复超时"
FIXSCOPE
chmod +x /app/docker/fix-scopes.sh

echo "[✓] supervisor 配置已生成"
echo ""
echo "======================================="
echo "  启动服务..."
echo "======================================="

/app/docker/fix-scopes.sh &

exec supervisord -n -c /etc/supervisor/supervisord.conf
