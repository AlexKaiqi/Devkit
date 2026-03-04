#!/usr/bin/env bash
# Devkit 项目状态诊断
# 用法: ./check.sh          人类可读输出
#       ./check.sh --json   机器可读 JSON（AI 解析用）
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
JSON_MODE=false
[[ "${1:-}" == "--json" ]] && JSON_MODE=true

# ── JSON 构建工具 ────────────────────────────

declare -a JSON_PARTS=()
json_kv() { JSON_PARTS+=("\"$1\":$2"); }

quote() { echo "\"$1\""; }

# ── 检查函数 ─────────────────────────────────

declare -a ISSUES=()

check_cmd() {
  local name="$1" label="${2:-$1}"
  if command -v "$name" &>/dev/null; then
    local ver
    ver=$("$name" --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+[.0-9]*' | head -1)
    $JSON_MODE || echo "  ✓ $label ${ver:+(v$ver)}" >&2
    echo "${ver:-ok}"
    return 0
  else
    $JSON_MODE || echo "  ✗ $label 未安装" >&2
    ISSUES+=("安装 $label")
    echo "missing"
    return 1
  fi
}

check_env_var() {
  local var="$1"
  if [ -n "${!var:-}" ]; then
    echo "set"
    return 0
  else
    echo "unset"
    return 1
  fi
}

check_port() {
  local port="$1" name="$2"
  if lsof -i ":$port" &>/dev/null; then
    $JSON_MODE || echo "  ✓ $name (:$port)" >&2
    echo "running"
    return 0
  else
    $JSON_MODE || echo "  - $name (:$port) 未运行" >&2
    echo "stopped"
    return 1
  fi
}

check_docker_container() {
  local name="$1"
  if command -v docker &>/dev/null && docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${name}$"; then
    $JSON_MODE || echo "  ✓ $name (Docker)" >&2
    echo "running"
    return 0
  elif command -v docker &>/dev/null && docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${name}$"; then
    $JSON_MODE || echo "  - $name (Docker, 已停止)" >&2
    echo "stopped"
    return 1
  else
    $JSON_MODE || echo "  - $name (Docker, 不存在)" >&2
    echo "missing"
    return 1
  fi
}

check_pip_pkg() {
  local pkg="$1"
  if "$SCRIPT_DIR/.venv/bin/pip" show "$pkg" &>/dev/null; then
    $JSON_MODE || echo "  ✓ $pkg" >&2
    echo "ok"
    return 0
  else
    $JSON_MODE || echo "  ✗ $pkg 未安装" >&2
    echo "missing"
    return 1
  fi
}

# ══════════════════════════════════════════════
# 1. 系统依赖
# ══════════════════════════════════════════════

$JSON_MODE || echo "=== 系统依赖 ==="

sys_node=$(check_cmd node Node)
sys_python=$(check_cmd python3 Python3)
sys_git=$(check_cmd git Git)
sys_docker=$(check_cmd docker Docker)
sys_cursor=$(check_cmd cursor "Cursor CLI")
sys_brew=$(check_cmd brew Homebrew)

python_ver="unknown"
if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
  python_ver=$("$SCRIPT_DIR/.venv/bin/python" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+[.0-9]*')
fi

json_kv "system" "{$(quote node):$(quote "$sys_node"),$(quote python):$(quote "$sys_python"),$(quote git):$(quote "$sys_git"),$(quote docker):$(quote "$sys_docker"),$(quote cursor):$(quote "$sys_cursor"),$(quote brew):$(quote "$sys_brew")}"

$JSON_MODE || echo ""

# ══════════════════════════════════════════════
# 2. .env 配置
# ══════════════════════════════════════════════

$JSON_MODE || echo "=== .env 配置 ==="

env_exists=false
if [ -f "$SCRIPT_DIR/.env" ]; then
  env_exists=true
  set -a; source "$SCRIPT_DIR/.env" 2>/dev/null; set +a
  $JSON_MODE || echo "  ✓ .env 存在"
else
  $JSON_MODE || echo "  ✗ .env 不存在（需从 .env.example 复制）"
  ISSUES+=("创建 .env: cp .env.example .env")
fi

env_doubao_appid=$(check_env_var DOUBAO_APPID)
env_doubao_token=$(check_env_var DOUBAO_TOKEN)
env_llm_key=$(check_env_var LLM_API_KEY)
env_llm_base=$(check_env_var LLM_BASE_URL)
env_gw_token=$(check_env_var OPENCLAW_GATEWAY_TOKEN)
env_hass_token=$(check_env_var HASS_TOKEN)
env_telegram=$(check_env_var TELEGRAM_BOT_TOKEN)
env_telegram_chat=$(check_env_var TELEGRAM_CHAT_ID)

$JSON_MODE || {
  [[ "$env_doubao_appid" == "set" ]] && echo "  ✓ DOUBAO_APPID" || echo "  ✗ DOUBAO_APPID 未设置"
  [[ "$env_doubao_token" == "set" ]] && echo "  ✓ DOUBAO_TOKEN" || echo "  ✗ DOUBAO_TOKEN 未设置"
  [[ "$env_llm_key" == "set" ]] && echo "  ✓ LLM_API_KEY" || echo "  ✗ LLM_API_KEY 未设置"
  [[ "$env_llm_base" == "set" ]] && echo "  ✓ LLM_BASE_URL" || echo "  - LLM_BASE_URL 未设置（可选）"
  [[ "$env_gw_token" == "set" ]] && echo "  ✓ OPENCLAW_GATEWAY_TOKEN" || echo "  - OPENCLAW_GATEWAY_TOKEN 未设置（可选）"
  [[ "$env_hass_token" == "set" ]] && echo "  - HASS_TOKEN 已设置" || echo "  - HASS_TOKEN 未设置（可选）"
  [[ "$env_telegram" == "set" ]] && echo "  - TELEGRAM_BOT_TOKEN 已设置" || echo "  - TELEGRAM_BOT_TOKEN 未设置（可选）"
  [[ "$env_telegram_chat" == "set" ]] && echo "  - TELEGRAM_CHAT_ID 已设置" || echo "  - TELEGRAM_CHAT_ID 未设置（可选）"
}

[[ "$env_doubao_appid" == "unset" ]] && ISSUES+=("设置 DOUBAO_APPID")
[[ "$env_doubao_token" == "unset" ]] && ISSUES+=("设置 DOUBAO_TOKEN")
[[ "$env_llm_key" == "unset" ]] && ISSUES+=("设置 LLM_API_KEY")

json_kv "env" "{$(quote exists):$env_exists,$(quote required):{$(quote DOUBAO_APPID):$(quote "$env_doubao_appid"),$(quote DOUBAO_TOKEN):$(quote "$env_doubao_token"),$(quote LLM_API_KEY):$(quote "$env_llm_key")},$(quote optional):{$(quote LLM_BASE_URL):$(quote "$env_llm_base"),$(quote OPENCLAW_GATEWAY_TOKEN):$(quote "$env_gw_token"),$(quote HASS_TOKEN):$(quote "$env_hass_token"),$(quote TELEGRAM_BOT_TOKEN):$(quote "$env_telegram"),$(quote TELEGRAM_CHAT_ID):$(quote "$env_telegram_chat")}}"

$JSON_MODE || echo ""

# ══════════════════════════════════════════════
# 3. Python .venv
# ══════════════════════════════════════════════

$JSON_MODE || echo "=== Python 虚拟环境 ==="

venv_exists=false
venv_python="missing"
declare -a pkg_entries=()

if [ -d "$SCRIPT_DIR/.venv" ] && [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
  venv_exists=true
  venv_python=$("$SCRIPT_DIR/.venv/bin/python" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1)
  $JSON_MODE || echo "  ✓ .venv 存在 (Python $venv_python)"

  for pkg in playwright paperscout papis khard khal vdirsyncer homeassistant-cli pandas numpy scipy matplotlib; do
    result=$(check_pip_pkg "$pkg")
    pkg_entries+=("$(quote "$pkg"):$(quote "$result")")
  done
else
  $JSON_MODE || echo "  ✗ .venv 不存在（运行 ./setup.sh 创建）"
  ISSUES+=("运行 ./setup.sh 创建 .venv")
fi

pkg_json=$(IFS=,; echo "${pkg_entries[*]}")
json_kv "venv" "{$(quote exists):$venv_exists,$(quote python):$(quote "$venv_python"),$(quote packages):{$pkg_json}}"

$JSON_MODE || echo ""

# ══════════════════════════════════════════════
# 4. CLI 工具
# ══════════════════════════════════════════════

$JSON_MODE || echo "=== CLI 工具 ==="

tool_gh=$(check_cmd gh "GitHub CLI")
tool_himalaya=$(check_cmd himalaya himalaya)
tool_rclone=$(check_cmd rclone rclone)
tool_pandoc=$(check_cmd pandoc pandoc)
tool_peekaboo=$(check_cmd peekaboo peekaboo)
tool_openclaw=$(check_cmd openclaw OpenClaw)

json_kv "tools" "{$(quote gh):$(quote "$tool_gh"),$(quote himalaya):$(quote "$tool_himalaya"),$(quote rclone):$(quote "$tool_rclone"),$(quote pandoc):$(quote "$tool_pandoc"),$(quote peekaboo):$(quote "$tool_peekaboo"),$(quote openclaw):$(quote "$tool_openclaw")}"

$JSON_MODE || echo ""

# ══════════════════════════════════════════════
# 5. 服务状态
# ══════════════════════════════════════════════

$JSON_MODE || echo "=== 服务状态 ==="

svc_searxng=$(check_docker_container searxng)
svc_stt=$(check_port "${STT_PROXY_PORT:-8787}" "豆包 STT 代理")
svc_gateway=$(check_port "${OPENCLAW_GATEWAY_PORT:-18789}" "OpenClaw Gateway")
svc_opencami=$(check_port "${OPENCAMI_PORT:-3000}" "OpenCami")
svc_voice=$(check_port "${VOICE_CHAT_PORT:-3001}" "语音对话")

json_kv "services" "{$(quote searxng):$(quote "$svc_searxng"),$(quote stt):$(quote "$svc_stt"),$(quote gateway):$(quote "$svc_gateway"),$(quote opencami):$(quote "$svc_opencami"),$(quote voice_chat):$(quote "$svc_voice")}"

$JSON_MODE || echo ""

# ══════════════════════════════════════════════
# 6. 外部配置
# ══════════════════════════════════════════════

$JSON_MODE || echo "=== 外部配置 ==="

himalaya_configured=false
if [ -f "$HOME/.config/himalaya/config.toml" ]; then
  himalaya_configured=true
  $JSON_MODE || echo "  ✓ himalaya 配置存在"
else
  $JSON_MODE || echo "  - himalaya 未配置 (~/.config/himalaya/config.toml)"
fi

vdirsyncer_configured=false
if [ -f "$HOME/.config/vdirsyncer/config" ]; then
  vdirsyncer_configured=true
  $JSON_MODE || echo "  ✓ vdirsyncer 配置存在"
else
  $JSON_MODE || echo "  - vdirsyncer 未配置 (~/.config/vdirsyncer/config)"
fi

openclaw_configured=false
if [ -f "$HOME/.openclaw/openclaw.json" ]; then
  openclaw_configured=true
  $JSON_MODE || echo "  ✓ OpenClaw 已配置"
else
  $JSON_MODE || echo "  ✗ OpenClaw 未配置（运行 openclaw onboard）"
  ISSUES+=("运行 openclaw onboard")
fi

json_kv "external" "{$(quote himalaya):$himalaya_configured,$(quote vdirsyncer):$vdirsyncer_configured,$(quote openclaw):$openclaw_configured}"

$JSON_MODE || echo ""

# ══════════════════════════════════════════════
# 7. 总结
# ══════════════════════════════════════════════

ready=true
next_arr=""
if [ ${#ISSUES[@]} -gt 0 ]; then
  ready=false
  declare -a next_json=()
  for issue in "${ISSUES[@]}"; do
    next_json+=("$(quote "$issue")")
  done
  next_arr=$(IFS=,; echo "${next_json[*]}")
fi

json_kv "ready" "$ready"
json_kv "next_steps" "[$next_arr]"

if $JSON_MODE; then
  echo "{$(IFS=,; echo "${JSON_PARTS[*]}")}"
else
  echo "=== 总结 ==="
  if $ready; then
    echo "  ✓ 项目就绪，可运行 ./start.sh 启动服务"
  else
    echo "  ✗ 有 ${#ISSUES[@]} 项需要处理："
    for issue in "${ISSUES[@]}"; do
      echo "    → $issue"
    done
  fi
  echo ""
fi
