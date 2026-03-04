# 踩坑手册

供 Agent 在开发过程中快速查阅。遇到报错时先搜索本文件中的错误关键词。

---

## Docker

### `npm error syscall spawn git`

npm 安装依赖时找不到 git。Dockerfile 中确保：

```dockerfile
apt-get install -y --no-install-recommends ... git
```

### `openclaw: Node.js v22.12+ is required`

基础镜像必须是 `node:22-slim` 或更高，不能用 `node:20`。

### `sed` 报 `unknown option to 's'`

替换包含 `/` 的字符串（如 URL）时，`sed` 默认分隔符 `/` 会冲突。
**不要用 `sed`**，改用 Python：

```bash
python3 -c "
import pathlib, sys
f = pathlib.Path(sys.argv[1])
f.write_text(f.read_text().replace(sys.argv[2], sys.argv[3]))
" /path/to/file "old_string" "new_string"
```

---

## OpenClaw / OpenCami

### `origin not allowed`

Gateway 日志显示 `origin=n/a` 并拒绝连接。
需要为 OpenCami 设置 Origin 环境变量：

```bash
OPENCAMI_ORIGIN="http://localhost:${OPENCAMI_PORT:-3000}"
```

### `missing required scope: operator.read`

新设备首次连接后无操作权限。需要执行：

```bash
openclaw devices rotate \
  --device <DEVICE_ID> --role operator \
  --scope operator.admin --scope operator.approvals \
  --scope operator.pairing --scope operator.read --scope operator.write
```

设备 ID 通过 `openclaw devices list` 获取。此步骤已在 `docker/entrypoint.sh` 中自动化。

### `allowedOrigins` 导致 Tunnel 域名被拒

`openclaw.json` 的 `controlUi.allowedOrigins` 必须包含 Tunnel 域名：

```json
"allowedOrigins": [
  "http://localhost:3000",
  "http://127.0.0.1:3000",
  "https://*.trycloudflare.com"
]
```

---

## Cloudflare Tunnel

### HTTP 530 错误

Docker 内 QUIC (UDP) 连接不稳定，强制使用 HTTP/2：

```bash
cloudflared tunnel --url http://localhost:3000 --protocol http2 --no-autoupdate
```

### 上传大音频文件失败 (Network connection lost)

Cloudflare 免费层对长耗时请求有限制。解决方式：
- 短音频（< 10s）走 Tunnel 正常
- 长音频直连内网 STT 端口 `http://localhost:8787`

### Tunnel URL 每次重启变化

免费 Quick Tunnel 行为。如需固定域名需注册 Cloudflare 账号绑定自有域名。
脚本中通过 `grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com'` 从日志提取 URL。

---

## 豆包语音识别 (STT)

### 服务凭据

```
DOUBAO_APPID=<火山引擎 AppID>
DOUBAO_TOKEN=<Access Token>
```

STT 代理监听端口由 `STT_PROXY_PORT`（默认 8787）控制。
代理将火山引擎 BigModel ASR WebSocket 协议包装为 Whisper 兼容 REST API。

### 验证

```bash
curl http://localhost:8787/health
curl -F "file=@test.wav" http://localhost:8787/v1/audio/transcriptions
```

---

## 豆包语音合成 (TTS)

与 STT 共用同一 `DOUBAO_APPID` / `DOUBAO_TOKEN`，但 **TTS 服务需在控制台单独开通**。

### 两代协议，不可混用

```
┌─────────────────────┬────────────────────────────────────────┬───────────────────────────────────────────┐
│                     │ 标准 TTS (V1)                          │ SeedTTS 2.0 (V3)                          │
├─────────────────────┼────────────────────────────────────────┼───────────────────────────────────────────┤
│ 端点                │ POST /api/v1/tts                       │ POST /api/v3/tts/unidirectional            │
│ Host                │ openspeech.bytedance.com               │ openspeech.bytedance.com                  │
│ 鉴权 Header         │ Authorization: Bearer;{TOKEN}          │ X-Api-App-Id / X-Api-Access-Key           │
│ 资源 ID             │ 无（走 cluster 字段）                    │ X-Api-Resource-Id: seed-tts-2.0           │
│ 请求体 - 音色字段    │ app.cluster + audio.voice_type         │ req_params.speaker                        │
│ 请求体 - 文本字段    │ request.text                           │ req_params.text                           │
│ 成功状态码          │ 3000                                    │ 0（最终）/ 20000000（中间数据块）            │
│ 响应格式            │ JSON { data: base64 }                   │ chunked JSON lines { data: base64 }       │
│ 音色命名            │ BV001_streaming, BV700_V2_streaming     │ saturn_*, *_uranus_bigtts                 │
└─────────────────────┴────────────────────────────────────────┴───────────────────────────────────────────┘
```

### `resource not granted` (code 3001)

TTS 服务未为当前 APPID 开通，或音色未授权。

排查步骤：
1. 确认 APPID 已开通 TTS 服务（控制台 → 语音技术 → 语音合成）
2. 大模型音色（`_bigtts` 后缀）需**单独下单**，部分免费音色需 0 元下单
3. 区分 1.0 和 2.0 资源：`volc.service_type.10029` = 1.0，`seed-tts-2.0` = 2.0

### `resource ID is mismatched with speaker` (code 55000000)

音色 ID 和 resource ID 不匹配。**绝对不能混用**：
- 标准音色 (`BV*_streaming`) → V1 API，cluster=`volcano_tts`
- 1.0 大模型音色 (`*_bigtts`, `*_moon_bigtts`) → V3 API，resource=`seed-tts-1.0`
- 2.0 大模型音色 (`saturn_*`, `*_uranus_bigtts`) → V3 API，resource=`seed-tts-2.0`

### V3 响应中 `code=20000000` 不是错误

V3 流式响应中每个中间数据块的 code 都是 `20000000`，最终块 code 为 `0`。
解析时只对 **非 0 且非 20000000** 的 code 报错：

```python
if code not in (0, 20000000):
    raise RuntimeError(f"TTS error: {code}")
```

### V1 请求示例

```python
body = {
    "app": {"appid": APPID, "token": "access_token", "cluster": "volcano_tts"},
    "user": {"uid": "agent"},
    "audio": {"voice_type": "BV700_V2_streaming", "encoding": "mp3", "speed_ratio": 1.0},
    "request": {"reqid": uuid.uuid4().hex, "text": "你好", "operation": "query"},
}
headers = {"Authorization": f"Bearer;{TOKEN}"}  # 注意是分号不是空格
resp = requests.post("https://openspeech.bytedance.com/api/v1/tts", headers=headers, json=body)
audio = base64.b64decode(resp.json()["data"])  # code == 3000 时
```

### V3 请求示例

```python
body = {
    "user": {"uid": "agent"},
    "req_params": {
        "text": "你好",
        "speaker": "zh_female_vv_uranus_bigtts",
        "audio_params": {"format": "mp3", "sample_rate": 24000},
    },
}
headers = {
    "X-Api-App-Id": APPID,
    "X-Api-Access-Key": TOKEN,
    "X-Api-Resource-Id": "seed-tts-2.0",
}
resp = requests.post("https://openspeech.bytedance.com/api/v3/tts/unidirectional",
                     headers=headers, json=body)
# 响应是 chunked JSON lines，每行解析 json，拼接 base64.b64decode(j["data"])
```

---

## Android 模拟器

### Chrome 首次运行弹出引导页

模拟器首次打开 Chrome 会显示 Welcome/Sign-in 流程，阻止直接导航。
`phone.sh` 已实现自动跳过：用 `adb shell dumpsys window` 检测 `FirstRunActivity`，
然后通过 `uiautomator dump` 定位按钮坐标并 `input tap` 点击。

### 访问宿主机 localhost

Android 模拟器的 `localhost` 指向模拟器自身，访问宿主机用 `10.0.2.2`：

```bash
adb shell am start -a android.intent.action.VIEW -d "http://10.0.2.2:3000"
```

---

## Playwright

### `Sync API inside asyncio loop`

Playwright 的 sync API 不能在已有 asyncio 事件循环中运行。
解决方式：在 `scope="module"` 的 fixture 中用 `sync_playwright()` 上下文管理器：

```python
@pytest.fixture(scope="module")
def pw():
    with sync_playwright() as p:
        yield p

@pytest.fixture(scope="module")
def browser(pw):
    b = pw.chromium.launch(headless=True)
    yield b
    b.close()
```

---

## 通用原则

- **不要用 `sed` 处理包含 URL 的字符串**，用 Python 替换
- **火山引擎的 TTS/STT 是独立服务**，开通一个不代表另一个也可用
- **V1 和 V3 是完全不同的协议**，鉴权方式、请求体结构、状态码都不同
- **Bearer 后面是分号**（`Bearer;token`），不是空格
- **Docker 内网络限制多**，优先 HTTP/2 而非 QUIC
- **Android 模拟器的 localhost ≠ 宿主机**，用 `10.0.2.2`
