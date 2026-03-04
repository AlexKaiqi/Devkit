#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================="
echo "  Devkit — 环境安装"
echo "========================================="
echo ""

# ── 1. 检查系统依赖 ──────────────────────────

check_cmd() {
  if ! command -v "$1" &>/dev/null; then
    echo "  ✗ $1 未安装"
    return 1
  fi
  echo "  ✓ $1 ($(command -v "$1"))"
  return 0
}

echo "[1/6] 检查系统依赖..."
missing=0
check_cmd node    || missing=1
check_cmd npm     || missing=1
check_cmd python3 || missing=1
check_cmd git     || missing=1
check_cmd cursor  || { echo "       Cursor CLI: https://www.cursor.com/"; missing=1; }

if [ "$missing" -eq 1 ]; then
  echo ""
  echo "请先安装缺失的依赖，然后重新运行此脚本。"
  echo "  brew install node python3 git"
  exit 1
fi
echo ""

# ── 2. .env 文件 ─────────────────────────────

echo "[2/6] 检查 .env..."
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
  echo "  已创建 .env（从 .env.example 复制）"
  echo "  ⚠️  请编辑 .env 填入实际凭据，然后重新运行此脚本"
  echo ""
  echo "  必填项:"
  echo "    DOUBAO_APPID       — 火山引擎语音识别 AppID"
  echo "    DOUBAO_TOKEN       — 火山引擎语音识别 Token"
  echo "    LLM_API_KEY        — LLM API Key (OpenAI 兼容)"
  exit 0
fi

source "$SCRIPT_DIR/.env"

required_vars=(DOUBAO_APPID DOUBAO_TOKEN)
for var in "${required_vars[@]}"; do
  if [ -z "${!var:-}" ]; then
    echo "  ✗ $var 未设置，请编辑 .env"
    exit 1
  fi
done
echo "  ✓ .env 已加载"
echo ""

# ── 3. Python 虚拟环境 ───────────────────────

echo "[3/6] 配置 Python 虚拟环境..."
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
  python3 -m venv "$SCRIPT_DIR/.venv"
  echo "  创建 .venv"
fi
"$SCRIPT_DIR/.venv/bin/pip" install -q -r "$SCRIPT_DIR/services/doubao-stt-proxy/requirements.txt"
echo "  ✓ 依赖已安装"
echo ""

# ── 4. OpenClaw ──────────────────────────────

echo "[4/6] 检查 OpenClaw..."
if ! command -v openclaw &>/dev/null; then
  echo "  安装 OpenClaw..."
  npm install -g openclaw
fi
echo "  ✓ OpenClaw $(openclaw --version 2>/dev/null | head -1 || echo 'installed')"

if [ ! -f "$HOME/.openclaw/openclaw.json" ]; then
  echo "  首次安装，运行 onboard..."
  openclaw onboard
fi
echo ""

# ── 5. 同步 Agent 配置 ───────────────────────

echo "[5/6] 同步 Agent 配置到 OpenClaw..."
bash "$SCRIPT_DIR/openclaw/sync.sh"
echo ""

# ── 6. OpenCami ──────────────────────────────

echo "[6/6] 检查 OpenCami..."
if ! npx opencami --help &>/dev/null 2>&1; then
  echo "  安装 OpenCami..."
  npm install -g opencami
fi
echo "  ✓ OpenCami 已安装"
echo ""

echo "========================================="
echo "  安装完成！"
echo ""
echo "  启动: ./start.sh"
echo "========================================="
