---
name: coding
always: false
keywords: [写代码, 实现, 开发, 重构, debug, 修复, fix, 代码, 函数, 类, 接口, 测试, review, 代码审查, 添加功能, 改一下, 帮我写, 生成代码, 脚本, 编程]
---
# Coding Skill

将编码子任务委派给 claude-internal 子代理执行，释放主模型的 context。

- `code_agent(prompt, workdir?, model?)` — 调用 claude-internal -p 非交互执行编码任务，返回结果
- 适合：实现新功能、修复 bug、重构代码、生成脚本、代码 review
- workdir 不填默认为项目根目录，model 可选 sonnet（默认）/ opus / haiku
- 长任务（>60s）会截断输出，建议拆分为子任务分批执行
- 执行前确认 prompt 清晰，包含：做什么、在哪里、验收标准
