#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-/opt/homebrew/share/android-commandlinetools}"
AVD_NAME="devkit"
ADB="$ANDROID_SDK_ROOT/platform-tools/adb"
EMULATOR="$ANDROID_SDK_ROOT/emulator/emulator"

export ANDROID_SDK_ROOT

# ── 参数 ──────────────────────────────────────

ACTION="${1:-start}"

usage() {
  echo "用法: ./phone.sh [start|stop|url|status]"
  echo ""
  echo "  start   启动 Android 模拟器并打开 OpenCami (默认)"
  echo "  stop    关闭模拟器"
  echo "  url     在已运行的模拟器中打开指定 URL"
  echo "  status  检查模拟器状态"
}

get_tunnel_url() {
  grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/cloudflared.log 2>/dev/null | tail -1 || true
}

wait_for_boot() {
  echo "  等待系统启动..."
  for i in $(seq 1 60); do
    BOOT=$("$ADB" -s emulator-5554 shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)
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

    # Chrome 首次运行：自动跳过设置引导
    FOCUS=$("$ADB" -s emulator-5554 shell dumpsys window 2>/dev/null | grep mCurrentFocus || true)
    if echo "$FOCUS" | grep -q "FirstRunActivity"; then
      echo "  跳过 Chrome 首次设置..."
      "$ADB" -s emulator-5554 shell input tap 540 2136 2>/dev/null; sleep 2
      for _ in 1 2 3; do
        BOUNDS=$("$ADB" -s emulator-5554 shell uiautomator dump /dev/tty 2>/dev/null | grep -oP 'text="No thanks".*?bounds="\[\K[0-9,\]\[]+' || true)
        if [ -n "$BOUNDS" ]; then
          X=$(echo "$BOUNDS" | grep -oP '^\d+' | head -1)
          X2=$(echo "$BOUNDS" | grep -oP '\[\K\d+' | tail -1)
          Y=$(echo "$BOUNDS" | grep -oP ',\K\d+' | head -1)
          Y2=$(echo "$BOUNDS" | grep -oP ',\K\d+' | tail -1)
          CX=$(( (X + X2) / 2 )); CY=$(( (Y + Y2) / 2 ))
          "$ADB" -s emulator-5554 shell input tap "$CX" "$CY" 2>/dev/null; sleep 2
        fi
        "$ADB" -s emulator-5554 shell dumpsys window 2>/dev/null | grep -q "FirstRunActivity" || break
        sleep 1
      done
    fi

    TUNNEL_URL=$(get_tunnel_url)
    if [ -n "$TUNNEL_URL" ]; then
      open_url_in_emulator "$TUNNEL_URL"
      echo ""
      echo "=== 虚拟手机已就绪 ==="
      echo "  Tunnel: $TUNNEL_URL"
    else
      CAMI_URL="http://10.0.2.2:${OPENCAMI_PORT:-3000}"
      open_url_in_emulator "$CAMI_URL"
      echo ""
      echo "=== 虚拟手机已就绪 ==="
      echo "  本地: $CAMI_URL (10.0.2.2 = 宿主机 localhost)"
      echo "  提示: 启动 Cloudflare Tunnel (./start.sh) 可获得 HTTPS + 语音支持"
    fi
    ;;

  stop)
    if "$ADB" devices 2>/dev/null | grep -q "emulator-5554"; then
      "$ADB" -s emulator-5554 emu kill 2>/dev/null
      echo "✓ 模拟器已关闭"
    else
      echo "模拟器未运行"
    fi
    ;;

  url)
    URL="${2:-}"
    if [ -z "$URL" ]; then
      URL=$(get_tunnel_url)
    fi
    if [ -z "$URL" ]; then
      echo "error: 未提供 URL 且无 Tunnel URL"
      echo "用法: ./phone.sh url https://example.com"
      exit 1
    fi
    open_url_in_emulator "$URL"
    ;;

  status)
    if "$ADB" devices 2>/dev/null | grep -q "emulator-5554"; then
      echo "模拟器: 运行中"
      "$ADB" -s emulator-5554 shell getprop ro.build.version.release 2>/dev/null | xargs -I{} echo "Android: {}"
    else
      echo "模拟器: 未运行"
    fi
    ;;

  *)
    usage
    exit 1
    ;;
esac
