# 决策：工具执行沙箱策略

## 背景

当前 agent 的 `exec`、`write_file`、`read_file` 工具直接操作宿主文件系统，默认工作目录为项目根目录。存在三类风险：

1. **误写源码** — agent 生成的临时文件直接落在 repo 里，污染项目结构
2. **危险命令** — `rm -rf`、`sudo` 等无防护
3. **无法回滚** — 文件写入后没有撤销机制

## 备选方案

| 方案 | 原理 | 代表 | 优点 | 缺点 |
|------|------|------|------|------|
| A. 容器沙箱 | 每次 exec 跑在 Docker/microVM | E2B, Code Interpreter | 完全隔离 | 对本地 runtime 太重；agent 需要真实访问 persona 文件、脚本、git |
| B. Git 快照回滚 | 每轮 tool 调用前 auto-stash | Aider | 可回滚 | 只保护 git tracked 文件；不防写到任意位置 |
| C. 工作目录隔离 | agent 读写限定在 workspace/ | ChatDev, MetaGPT | 简单 | 太死板，agent 需要操作 persona、ops 脚本、STATUS.md 等 |
| **D. 分区权限 + 命令过滤** | 按路径分安全区/受控区/禁区，exec 做命令黑名单 | Claude Code permission modes | 贴合本地 agent 场景、轻量、可渐进增强 | 不能防所有 edge case |
| E. OverlayFS | 文件系统叠加层 | Container runtimes | 源文件不变 | Linux only，需 root |

## 决策

采用**方案 D：分区权限 + 命令过滤**，辅以 Git 快照（方案 B）作为补充回滚手段。

理由：
- Devkit 是个人本地 runtime，agent 需要真实读写文件系统（写日记、执行脚本、管理知识库），不能完全隔离。
- 分区策略贴合现有 workspace 结构，安全区覆盖 agent 日常操作路径，受控区保护项目源码。
- 命令过滤防止最危险的操作，但不过度限制 agent 的能力。
- Git stash 作为兜底：会话开始时如果工作区有未提交改动，先 stash；agent 写坏了可以恢复。

## 设计

### 路径分区

```
安全区（自由读写）                  受控区（需确认 / dry-run）        禁区（拒绝）
────────────────────────          ─────────────────────────        ─────────────
implementation/assets/persona/    implementation/runtime/           项目根目录以外
implementation/data/              implementation/channels/          /etc, /usr, /var
/tmp/devkit-*                     implementation/ops/               ~/.ssh, ~/.gnupg
                                  implementation/tests/             .env, .env.*
                                  implementation/services/          *.pem, *_key, *_secret*
                                  design/
                                  requirements/
```

**规则**：
- `read_file`：安全区和受控区均可读（读操作风险低）；禁区拒绝。
- `write_file`：安全区自由写；受控区返回 `[confirm_required]` 标记，让 agent 请求用户确认；禁区拒绝。
- `exec`：工作目录默认为项目根目录（不变），但增加命令过滤层。

### 命令过滤

`exec` 工具增加两层防护：

**黑名单模式匹配**（拒绝执行）：
```python
BLOCKED_PATTERNS = [
    r"\brm\s+-[^\s]*r[^\s]*f",   # rm -rf / rm -fr
    r"\bsudo\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\b>\s*/dev/sd",
    r"\bchmod\s+777",
    r"\bcurl\b.*\|\s*(ba)?sh",    # curl | sh
]
```

**危险命令警告**（返回 `[confirm_required]`，不直接拒绝）：
```python
WARN_PATTERNS = [
    r"\bgit\s+push\s+.*--force",
    r"\bgit\s+reset\s+--hard",
    r"\brm\s+-r\b",               # rm -r（非 rm -rf）
    r"\bpip\s+install\b",
]
```

### 确认机制

当 `write_file` 写入受控区或 `exec` 命中 WARN_PATTERNS 时：

1. Tool handler 返回 `[confirm_required] 即将执行: {描述}。请确认是否继续。`
2. Agent 将此信息透传给用户，等用户确认后再次调用（附带 `confirmed: true` 参数）。
3. 带 `confirmed: true` 的调用跳过确认检查，直接执行。

```python
# write_file schema 增加可选参数
"confirmed": {"type": "boolean", "description": "用户已确认（受控区写入时需要）"}

# exec schema 增加可选参数
"confirmed": {"type": "boolean", "description": "用户已确认（危险命令时需要）"}
```

### Git 快照兜底

在 `LocalAgent.__init__` 中，检查工作区状态：

```python
# 如果有未提交改动，自动 stash
git stash push -m "devkit-agent-session-{timestamp}" --include-untracked
```

会话结束时不自动 pop（避免冲突），但记录 stash ref 到日志，方便人工恢复。

### 实现位置

权限检查逻辑放在 `tools/__init__.py` 的 `run_tool()` 中，作为统一拦截层：

```python
async def run_tool(name: str, arguments: dict, session_key: str = "") -> str:
    td = _REGISTRY.get(name)
    if not td:
        return f"[error] Unknown tool: {name}"

    # 权限检查
    denial = check_permission(name, arguments)
    if denial:
        return denial

    ctx = ToolContext(session_key=session_key, data=_CONTEXT)
    return await td.handler(arguments, ctx)
```

`check_permission()` 集中在一个新文件 `tools/sandbox.py` 中，职责单一。

### 配置

分区规则和命令过滤模式通过 `implementation/assets/persona/TOOLS.md` 或环境变量配置，不硬编码：

```python
# 环境变量覆盖
SANDBOX_MODE = os.environ.get("SANDBOX_MODE", "enforced")  # enforced | warn | disabled
```

开发调试时可设为 `disabled` 跳过所有检查。

## 文件变更

| 文件 | 变更 |
|------|------|
| `runtime/tools/sandbox.py` | 新建：路径分区规则、命令过滤、check_permission() |
| `runtime/tools/__init__.py` | run_tool() 中调用 check_permission() |
| `runtime/tools/exec.py` | schema 增加 confirmed 参数 |
| `runtime/tools/write_file.py` | schema 增加 confirmed 参数 |

## 不做什么

- 不做容器隔离 — 对个人本地 runtime 收益不大、复杂度太高。
- 不做 OverlayFS — 平台限制（macOS 无原生支持）。
- 不做全量白名单 — agent 的价值在于灵活调用工具，过度限制会削弱能力。
- 不对 `read_file` 做受控区确认 — 读操作风险极低，加确认只会拖慢交互。

## 渐进增强路径

1. **P0（本次）**：命令黑名单 + 路径分区 + confirmed 机制
2. **P1**：Git auto-stash 兜底
3. **P2**：审计日志 — 所有 exec/write 操作记录到 `implementation/data/tool-audit/`
4. **P3**：用户自定义规则 — 允许在 persona 配置中扩展安全区/受控区路径
