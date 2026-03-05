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

echo "[1/9] 检查系统依赖..."
missing=0
check_cmd node    || missing=1
check_cmd npm     || missing=1
check_cmd python3 || missing=1
check_cmd git     || missing=1
check_cmd cursor  || { echo "       Cursor CLI: https://www.cursor.com/"; missing=1; }

if [ "$missing" -eq 1 ]; then
  echo ""
  echo "请先安装缺失的依赖，然后重新运行此脚本。"
  echo "  brew install node python@3.12 git"
  exit 1
fi
echo ""

# ── 2. .env 文件 ─────────────────────────────

echo "[2/9] 检查 .env..."
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
  # Auto-generate OPENCLAW_GATEWAY_TOKEN
  TOKEN=$(openssl rand -hex 16 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(16))")
  sed -i '' "s/^OPENCLAW_GATEWAY_TOKEN=$/OPENCLAW_GATEWAY_TOKEN=$TOKEN/" "$SCRIPT_DIR/.env"
  echo "  已创建 .env（从 .env.example 复制）"
  echo "  已自动生成 OPENCLAW_GATEWAY_TOKEN"
  echo "  ⚠️  请编辑 .env 填入实际凭据，然后重新运行此脚本"
  echo ""
  echo "  必填项:"
  echo "    DOUBAO_APPID       — 火山引擎语音 AppID"
  echo "    DOUBAO_TOKEN       — 火山引擎语音 Token"
  echo ""
  echo "  LLM 配置在后续 openclaw onboard 步骤中完成（不在 .env 里）"
  exit 0
fi

source "$SCRIPT_DIR/.env"

required_vars=(DOUBAO_APPID DOUBAO_TOKEN OPENCLAW_GATEWAY_TOKEN)
for var in "${required_vars[@]}"; do
  if [ -z "${!var:-}" ]; then
    echo "  ✗ $var 未设置，请编辑 .env"
    exit 1
  fi
done
echo "  ✓ .env 已加载"
echo ""

# ── 3. Python 虚拟环境 ───────────────────────

echo "[3/9] 配置 Python 虚拟环境..."

PYTHON_BIN="python3"
if [ -x "/opt/homebrew/opt/python@3.12/bin/python3.12" ]; then
  PYTHON_BIN="/opt/homebrew/opt/python@3.12/bin/python3.12"
fi

if [ ! -d "$SCRIPT_DIR/.venv" ]; then
  "$PYTHON_BIN" -m venv "$SCRIPT_DIR/.venv"
  echo "  创建 .venv ($("$SCRIPT_DIR/.venv/bin/python" --version))"
fi

echo "  安装 Python 依赖..."
"$SCRIPT_DIR/.venv/bin/pip" install -q --upgrade pip
"$SCRIPT_DIR/.venv/bin/pip" install -q -r "$SCRIPT_DIR/requirements.txt"
echo "  ✓ Python 依赖已安装"
echo ""

# ── 3b. Playwright 浏览器 ────────────────────

if [ ! -d "$HOME/Library/Caches/ms-playwright" ]; then
  echo "  安装 Playwright Chromium..."
  "$SCRIPT_DIR/.venv/bin/playwright" install chromium
  echo "  ✓ Playwright Chromium 已安装"
else
  echo "  ✓ Playwright Chromium 已存在"
fi
echo ""

# ── 4. Homebrew CLI 工具 ─────────────────────

echo "[4/9] 安装 CLI 工具 (Homebrew)..."

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

# ── 5. OpenClaw ──────────────────────────────

echo "[5/9] 检查 OpenClaw..."
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

# ── 6. 同步 Agent 配置 ───────────────────────

echo "[6/9] 同步 Agent 配置到 OpenClaw..."
bash "$SCRIPT_DIR/openclaw/sync.sh"
echo ""

# ── 7. OpenCami ──────────────────────────────

echo "[7/9] 检查 OpenCami..."
if ! npx opencami --help &>/dev/null 2>&1; then
  echo "  安装 OpenCami..."
  npm install -g opencami
fi
echo "  ✓ OpenCami 已安装"
echo ""

# ── 8. Docker 检查 ───────────────────────────

echo "[8/9] 检查 Docker (SearXNG 依赖)..."
if command -v docker &>/dev/null; then
  echo "  ✓ Docker 已安装"
  if docker info &>/dev/null 2>&1; then
    echo "  ✓ Docker 正在运行"
  else
    echo "  ⚠️  Docker 未运行，请启动 Docker Desktop（SearXNG 需要）"
  fi
else
  echo "  ⚠️  Docker 未安装，SearXNG 搜索引擎将不可用"
  echo "     安装: https://www.docker.com/products/docker-desktop/"
fi
echo ""

# ── 9. 定时巡检 (launchd) ────────────────────

PLIST_SRC="$SCRIPT_DIR/services/heartbeat/com.devkit.heartbeat.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.devkit.heartbeat.plist"

if [ -f "$PLIST_SRC" ]; then
  echo "[9/9] 配置定时巡检 (heartbeat)..."
  if [ -f "$PLIST_DST" ]; then
    echo "  ✓ launchd plist 已安装"
  else
    cp "$PLIST_SRC" "$PLIST_DST"
    echo "  ✓ launchd plist 已安装到 ~/Library/LaunchAgents/"
    echo "  启用: launchctl load $PLIST_DST"
    echo "  (需要配置 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID 后才有效)"
  fi
  echo ""
fi

echo "========================================="
echo "  安装完成！"
echo ""
echo "  启动: ./start.sh"
echo ""
echo "  可选手动配置:"
echo "    - himalaya: ~/.config/himalaya/config.toml (邮件)"
echo "    - vdirsyncer: ~/.config/vdirsyncer/config (日历同步)"
echo "    - Telegram: .env 中设置 TELEGRAM_BOT_TOKEN + CHAT_ID"
echo "    - 巡检: launchctl load ~/Library/LaunchAgents/com.devkit.heartbeat.plist"
echo "========================================="
