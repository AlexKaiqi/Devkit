#!/usr/bin/env bash
set -euo pipefail

echo "停止服务..."

for port in 3000 18789 8787; do
  pids=$(lsof -t -i ":$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "$pids" | xargs kill -9 2>/dev/null || true
    echo "  ✓ 已停止 :$port"
  fi
done

echo "done"
