#!/usr/bin/env bash
set -uo pipefail

OPS_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$OPS_DIR/../.." && pwd)"
JSON_MODE=false
[[ "${1:-}" == "--json" ]] && JSON_MODE=true

declare -a JSON_PARTS=()
json_kv() { JSON_PARTS+=("\"$1\":$2"); }
quote() { echo "\"$1\""; }

declare -a ISSUES=()

check_cmd() {
  local name="$1" label="${2:-$1}"
  if command -v "$name" &>/dev/null; then
    local ver
    ver=$("$name" --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+[.0-9]*' | head -1)
    $JSON_MODE || echo "  ✓ $label ${ver:+(v$ver)}" >&2
    echo "${ver:-ok}"
  else
    $JSON_MODE || echo "  ✗ $label 未安装" >&2
    ISSUES+=("安装 $label")
    echo "missing"
  fi
}

check_env_var() {
  local var="$1"
  if [ -n "${!var:-}" ]; then
    echo "set"
  else
    echo "unset"
  fi
}

check_port() {
  local port="$1" name="$2"
  if lsof -i ":$port" &>/dev/null; then
    $JSON_MODE || echo "  ✓ $name (:$port)" >&2
    echo "running"
  else
    $JSON_MODE || echo "  - $name (:$port) 未运行" >&2
    echo "stopped"
  fi
}

check_docker_container() {
  local name="$1"
  if command -v docker &>/dev/null && docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${name}$"; then
    $JSON_MODE || echo "  ✓ $name (Docker)" >&2
    echo "running"
  elif command -v docker &>/dev/null && docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${name}$"; then
    $JSON_MODE || echo "  - $name (Docker, 已停止)" >&2
    echo "stopped"
  else
    $JSON_MODE || echo "  - $name (Docker, 不存在)" >&2
    echo "missing"
  fi
}

check_pip_pkg() {
  local pkg="$1"
  if "$REPO_ROOT/.venv/bin/pip" show "$pkg" &>/dev/null; then
    $JSON_MODE || echo "  ✓ $pkg" >&2
    echo "ok"
  else
    $JSON_MODE || echo "  ✗ $pkg 未安装" >&2
    echo "missing"
  fi
}

$JSON_MODE || echo "=== 系统依赖 ==="
sys_node=$(check_cmd node Node)
sys_python=$(check_cmd python3 Python3)
sys_git=$(check_cmd git Git)
sys_docker=$(check_cmd docker Docker)
sys_cursor=$(check_cmd cursor "Cursor CLI")
sys_brew=$(check_cmd brew Homebrew)
json_kv "system" "{$(quote node):$(quote "$sys_node"),$(quote python):$(quote "$sys_python"),$(quote git):$(quote "$sys_git"),$(quote docker):$(quote "$sys_docker"),$(quote cursor):$(quote "$sys_cursor"),$(quote brew):$(quote "$sys_brew")}"
$JSON_MODE || echo ""

$JSON_MODE || echo "=== .env 配置 ==="
if [ -f "$REPO_ROOT/.env" ]; then
  set -a; source "$REPO_ROOT/.env" 2>/dev/null; set +a
  env_exists=true
  $JSON_MODE || echo "  ✓ .env 存在"
else
  env_exists=false
  $JSON_MODE || echo "  ✗ .env 不存在（需从 .env.example 复制）"
  ISSUES+=("创建 .env: cp .env.example .env")
fi
for var in DOUBAO_APPID DOUBAO_TOKEN LLM_API_KEY LLM_BASE_URL; do
  value=$(check_env_var "$var")
  [[ "$value" == "unset" ]] && ISSUES+=("设置 $var")
  if ! $JSON_MODE; then
    if [[ "$value" == "set" ]]; then
      echo "  ✓ $var"
    else
      echo "  ✗ $var 未设置"
    fi
  fi
done
json_kv "env" "{$(quote exists):$env_exists}"
$JSON_MODE || echo ""

$JSON_MODE || echo "=== Python 虚拟环境 ==="
venv_exists=false
venv_python="missing"
if [ -d "$REPO_ROOT/.venv" ] && [ -x "$REPO_ROOT/.venv/bin/python" ]; then
  venv_exists=true
  venv_python=$("$REPO_ROOT/.venv/bin/python" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+[.0-9]*')
  $JSON_MODE || echo "  ✓ .venv 存在 (Python $venv_python)"
  for pkg in fastapi uvicorn aiohttp python-telegram-bot playwright paperscout papis khard khal vdirsyncer homeassistant-cli pandas numpy scipy matplotlib; do
    check_pip_pkg "$pkg" >/dev/null
  done
else
  $JSON_MODE || echo "  ✗ .venv 不存在（运行 ./setup.sh 创建）"
  ISSUES+=("运行 ./setup.sh 创建 .venv")
fi
json_kv "venv" "{$(quote exists):$venv_exists,$(quote python):$(quote "$venv_python")}"
$JSON_MODE || echo ""

$JSON_MODE || echo "=== 服务状态 ==="
svc_searxng=$(check_docker_container searxng)
svc_stt=$(check_port "${STT_PROXY_PORT:-8787}" "豆包 STT 代理")
svc_voice=$(check_port "${VOICE_CHAT_PORT:-3001}" "风铃")
svc_timer=$(check_port "${TIMER_API_PORT:-8789}" "Timer API")
json_kv "services" "{$(quote searxng):$(quote "$svc_searxng"),$(quote stt):$(quote "$svc_stt"),$(quote fengling):$(quote "$svc_voice"),$(quote timer_api):$(quote "$svc_timer")}"
$JSON_MODE || echo ""

ready=true
if [ ${#ISSUES[@]} -gt 0 ]; then
  ready=false
fi
json_kv "ready" "$ready"

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
