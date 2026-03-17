---
name: coding
always: false
keywords: [写代码, 实现, 开发, 重构, debug, 修复, fix, 代码, 函数, 类, 接口, 测试, review, 代码审查, 添加功能, 改一下, 帮我写, 生成代码, 脚本, 编程, 安装, 配置, 部署, 环境, 跑起来, 运行, 调试, 报错, 错误, 崩了, 挂了, bug]
---
# Coding Skill

通过 Claude Code CLI 执行编码任务（spawn `claude-internal -p` 进程，经 OpenRouter proxy 调用 Claude 模型）。

- `code_agent(prompt, workdir?, model?)` — 调用 Claude Code CLI 非交互执行编码任务，返回结果
- 适合：实现新功能、修复 bug、重构代码、生成脚本、代码 review
- workdir 不填默认为项目根目录，model 可选 sonnet（默认）/ opus / haiku
- 单次调用预算上限 $0.50，超时 5 分钟
- 长任务建议拆分为子任务分批执行
- 执行前确认 prompt 清晰，包含：做什么、在哪里、验收标准
- 依赖：OpenRouter proxy 服务（端口 9999）需提前启动
