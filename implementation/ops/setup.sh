#!/usr/bin/env bash
set -euo pipefail

OPS_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$OPS_DIR/../.." && pwd)"
cd "$REPO_ROOT"

echo "========================================="
echo "  Devkit — 环境安装"
echo "========================================="
echo ""

check_cmd() {
  if ! command -v "$1" &>/dev/null; then
    echo "  ✗ $1 未安装"
    return 1
  fi
  echo "  ✓ $1 ($(command -v "$1"))"
  return 0
}

echo "[1/7] 检查系统依赖..."
missing=0
check_cmd python3 || missing=1
check_cmd git || missing=1
if [ "$missing" -eq 1 ]; then
  echo ""
  echo "请先安装缺失依赖，然后重新运行此脚本。"
  echo "  brew install python@3.12 git"
  exit 1
fi
echo ""

echo "[2/7] 检查 .env..."
if [ ! -f "$REPO_ROOT/.env" ]; then
  cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
  echo "  已创建 .env（从 .env.example 复制）"
  echo "  ⚠️  请编辑 .env 填入实际凭据，然后重新运行此脚本"
  exit 0
fi
source "$REPO_ROOT/.env"
for var in DOUBAO_APPID DOUBAO_TOKEN LLM_API_KEY LLM_BASE_URL; do
  if [ -z "${!var:-}" ]; then
    echo "  ✗ $var 未设置，请编辑 .env"
    exit 1
  fi
done
echo "  ✓ .env 已加载"
echo ""

echo "[3/7] 配置 Python 虚拟环境..."
PYTHON_BIN="python3"
if [ -x "/opt/homebrew/opt/python@3.12/bin/python3.12" ]; then
  PYTHON_BIN="/opt/homebrew/opt/python@3.12/bin/python3.12"
fi
if [ ! -d "$REPO_ROOT/.venv" ]; then
  "$PYTHON_BIN" -m venv "$REPO_ROOT/.venv"
  echo "  创建 .venv ($("$REPO_ROOT/.venv/bin/python" --version))"
fi
echo "  安装 Python 依赖..."
"$REPO_ROOT/.venv/bin/pip" install -q --upgrade pip
"$REPO_ROOT/.venv/bin/pip" install -q -r "$REPO_ROOT/requirements.txt"
echo "  ✓ Python 依赖已安装"
echo ""

if [ ! -d "$HOME/Library/Caches/ms-playwright" ]; then
  echo "  安装 Playwright Chromium..."
  "$REPO_ROOT/.venv/bin/playwright" install chromium
  echo "  ✓ Playwright Chromium 已安装"
else
  echo "  ✓ Playwright Chromium 已存在"
fi
echo ""

echo "[4/7] 安装 CLI 工具 (Homebrew)..."
BREW_TOOLS=(gh himalaya rclone pandoc peekaboo)
for tool in "${BREW_TOOLS[@]}"; do
  if command -v "$tool" &>/dev/null; then
    echo "  ✓ $tool"
  else
    echo "  安装 $tool..."
    brew install "$tool" 2>/dev/null || echo "  ⚠️  $tool 安装失败，可手动重试: brew install $tool"
  fi
done
echo ""

echo "[5/7] 检查 Docker (SearXNG 依赖)..."
if command -v docker &>/dev/null; then
  echo "  ✓ Docker 已安装"
  if docker info &>/dev/null 2>&1; then
    echo "  ✓ Docker 正在运行"
  else
    echo "  ⚠️  Docker 未运行，请启动 Docker Desktop（SearXNG 需要）"
  fi
else
  echo "  ⚠️  Docker 未安装，SearXNG 搜索引擎将不可用"
fi
echo ""

PLIST_SRC="$REPO_ROOT/implementation/ops/heartbeat/com.devkit.heartbeat.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.devkit.heartbeat.plist"
if [ -f "$PLIST_SRC" ]; then
  echo "[6/7] 配置定时巡检 (heartbeat)..."
  if [ -f "$PLIST_DST" ]; then
    echo "  ✓ launchd plist 已安装"
  else
    cp "$PLIST_SRC" "$PLIST_DST"
    echo "  ✓ launchd plist 已安装到 ~/Library/LaunchAgents/"
    echo "  启用: launchctl load $PLIST_DST"
  fi
  echo ""
fi

echo "========================================="
echo "  安装完成！"
echo ""
echo "  启动: ./start.sh"
echo "========================================="
