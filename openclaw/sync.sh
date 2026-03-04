#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="$HOME/.openclaw/workspace"

FILES=(IDENTITY.md SOUL.md USER.md AGENTS.md TOOLS.md HEARTBEAT.md)

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

echo ""
if [ "$changed" -gt 0 ]; then
  echo "$changed file(s) synced to $TARGET"
  if lsof -i :18789 >/dev/null 2>&1; then
    echo ""
    echo "Gateway is running. Restart to apply changes:"
    echo "  openclaw gateway restart"
  fi
else
  echo "All files up to date."
fi
