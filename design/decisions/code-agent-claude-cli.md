# code_agent — Claude Code CLI 调用与方法论上下文注入

> 状态：已实施
> 日期：2026-03-17

## 问题

进程内子代理复用 deepseek，编码能力受限于主模型。之前尝试直接 subprocess 调用 `claude-internal` 在非 TTY 下卡住。同时，当风铃通过 code_agent 委托 Claude CLI 执行编码任务时，子进程不感知当前 Feature 的方法论状态，可能在 requirements/design 阶段就直接写代码，绕过门控。

## 决策

1. spawn `claude-internal -p` + OpenRouter proxy 翻译，替代进程内子代理
2. 通过 `--append-system-prompt` 将方法论上下文注入 Claude CLI，使其遵循门控约束

## 关键设计选择

### CLI subprocess vs API 直调

选择 CLI subprocess。`claude-internal -p` 自带 agent loop、工具系统（Read/Write/Edit/Glob/Grep/Bash）、CLAUDE.md 自动加载，无需自建编码代理能力。trade-off 是进程启动开销和输出格式依赖，但对于编码任务来说，Claude CLI 的完整 agent 能力远超 API 直调。

### OpenRouter proxy

模型名翻译（`claude-sonnet-4-5` → OpenRouter 格式）+ SSE thinking block 过滤 + null 值清理。解决 Claude CLI 对模型名和响应格式的特定要求。proxy 运行在 `localhost:9999`，通过 `ANTHROPIC_BASE_URL` 环境变量让 CLI 连接。

### `--append-system-prompt` 注入方法论

不覆盖默认 prompt（保留 CLAUDE.md），仅追加门控状态。这样 CLI 既能读到仓库的 CLAUDE.md 指引，也能感知当前 Feature 的方法论阶段和门控结果。

方法论传递方案：
1. `ctx.get("methodology_engine")` 获取引擎实例（复用 agent.py 中已有的注入模式）
2. `build_methodology_context(engine, session_key)` 构建状态文本
3. `--append-system-prompt` 作为 CLI 参数传递

降级策略：engine 不存在、构建失败或返回空字符串时，静默跳过，不附加 `--append-system-prompt`。

### 安全控制

- `--max-budget-usd 0.50`：单次调用预算上限
- `--allowedTools Bash,Read,Write,Edit,Glob,Grep`：白名单工具
- `--no-session-persistence`：不保留会话状态
- 5 分钟超时 + 强制 kill

## 替代方案

- **进程内子代理**：编码能力受限于主模型（deepseek），且需自建工具系统
- **API 直调 Claude**：需自建 agent loop 和工具调用，复杂度高
- **方法论拦截器（hard block）**：在 CLI 内部运行拦截器不现实（无法注入运行时组件），靠 prompt 约束是可行的折中
