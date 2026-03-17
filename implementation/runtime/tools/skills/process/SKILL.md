---
name: process
always: false
keywords: [后台, background, 进程, process, 运行中, 任务状态, 后台任务, 长时间, 异步执行, 后台执行, 查看进程, 杀死进程, 进程列表, 正在跑, 还在跑]
---
# Process Skill

后台进程管理能力。用于启动长时间运行的命令并在后台追踪。

- `process_start(command, label?)` — 后台启动命令，返回 pid
- `process_list()` — 列出所有后台进程及状态
- `process_log(pid, lines=50)` — 查看某进程的输出日志
- `process_kill(pid)` — 终止后台进程
- `process_wait(pid, timeout=30)` — 等待进程完成并返回结果

典型场景：
- "帮我后台跑这个脚本，完成后通知我"
- "刚才那个编译还在跑吗"
- "把那个进程停掉"
