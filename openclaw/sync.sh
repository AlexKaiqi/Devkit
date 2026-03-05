#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET="$HOME/.openclaw/workspace"

[ -f "$PROJECT_DIR/.env" ] && { set -a; source "$PROJECT_DIR/.env" 2>/dev/null; set +a; }
OPENCLAW_GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"

FILES=(IDENTITY.md SOUL.md USER.md AGENTS.md TOOLS.md HEARTBEAT.md MEMORY.md)

if [ ! -d "$TARGET" ]; then
  echo "error: OpenClaw workspace not found at $TARGET"
  exit 1
fi

changed=0
for f in "${FILES[@]}"; do
  src="$SCRIPT_DIR/$f"
  dst="$TARGET/$f"
  if [ ! -f "$src" ]; then
    echo "skip: $f (not found in project)"
    continue
  fi
  if [ -f "$dst" ] && diff -q "$src" "$dst" >/dev/null 2>&1; then
    echo "  ok: $f (no change)"
  else
    cp "$src" "$dst"
    echo "  >>: $f (synced)"
    changed=$((changed + 1))
  fi
done

# memory/ 目录同步（每日日志）
mkdir -p "$TARGET/memory"
if [ -d "$SCRIPT_DIR/memory" ]; then
  for f in "$SCRIPT_DIR/memory/"*.md; do
    [ -f "$f" ] || continue
    fname=$(basename "$f")
    dst="$TARGET/memory/$fname"
    if [ -f "$dst" ] && diff -q "$f" "$dst" >/dev/null 2>&1; then
      : # no change
    else
      cp "$f" "$dst"
      echo "  >>: memory/$fname (synced)"
      changed=$((changed + 1))
    fi
  done
fi

echo ""
if [ "$changed" -gt 0 ]; then
  echo "$changed file(s) synced to $TARGET"
  if lsof -i ":$OPENCLAW_GATEWAY_PORT" >/dev/null 2>&1; then
    echo ""
    echo "Gateway is running. Restart to apply changes:"
    echo "  openclaw gateway restart"
  fi
else
  echo "All files up to date."
fi
