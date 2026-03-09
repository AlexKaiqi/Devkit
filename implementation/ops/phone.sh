#!/usr/bin/env bash
set -euo pipefail

ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-/opt/homebrew/share/android-commandlinetools}"
AVD_NAME="devkit"
ADB="$ANDROID_SDK_ROOT/platform-tools/adb"
EMULATOR="$ANDROID_SDK_ROOT/emulator/emulator"
ACTION="${1:-start}"

export ANDROID_SDK_ROOT

usage() {
  echo "用法: ./phone.sh [start|stop|url|status]"
}

get_tunnel_url() {
  grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/cloudflared.log 2>/dev/null | tail -1 || true
}

wait_for_boot() {
  echo "  等待系统启动..."
  for _ in $(seq 1 60); do
    BOOT=$("$ADB" -s emulator-5554 shell getprop sys.boot_completed 2>/dev/null | tr -d '' || true)
    if [ "$BOOT" = "1" ]; then
      echo "  ✓ 系统已就绪"
      return 0
    fi
    sleep 2
  done
  echo "  ✗ 启动超时"
  return 1
}

open_url_in_emulator() {
  local url="$1"
  "$ADB" -s emulator-5554 shell am start -a android.intent.action.VIEW -d "$url" 2>/dev/null
  echo "  ✓ 已在模拟器中打开: $url"
}

case "$ACTION" in
  start)
    if "$ADB" devices 2>/dev/null | grep -q "emulator-5554"; then
      echo "模拟器已在运行"
    else
      echo "启动 Android 模拟器 ($AVD_NAME)..."
      "$EMULATOR" -avd "$AVD_NAME" -no-snapshot -gpu host -no-metrics 2>/dev/null &
      disown
      wait_for_boot
    fi
    sleep 2
    TUNNEL_URL=$(get_tunnel_url)
    if [ -n "$TUNNEL_URL" ]; then
      open_url_in_emulator "$TUNNEL_URL"
      echo "=== 虚拟手机已就绪 ==="
      echo "  Tunnel: $TUNNEL_URL"
    else
      FENGLING_URL="http://10.0.2.2:${VOICE_CHAT_PORT:-3001}"
      open_url_in_emulator "$FENGLING_URL"
      echo "=== 虚拟手机已就绪 ==="
      echo "  本地: $FENGLING_URL"
      echo "  提示: 启动 Cloudflare Tunnel (./start.sh) 可获得 HTTPS + 语音支持"
    fi
    ;;
  stop)
    "$ADB" -s emulator-5554 emu kill 2>/dev/null || true
    ;;
  url)
    URL="${2:-$(get_tunnel_url)}"
    [ -z "$URL" ] && { echo "error: 未提供 URL 且无 Tunnel URL"; exit 1; }
    open_url_in_emulator "$URL"
    ;;
  status)
    if "$ADB" devices 2>/dev/null | grep -q "emulator-5554"; then
      echo "模拟器: 运行中"
    else
      echo "模拟器: 未运行"
    fi
    ;;
  *)
    usage
    exit 1
    ;;
esac
