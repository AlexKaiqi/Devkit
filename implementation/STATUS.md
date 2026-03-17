# 当前状态

> 最后更新：2026-03-17

## 当前状态

仓库已重组为 `requirements/`、`design/`、`implementation/` 三层：

- `requirements/` 负责产品需求、能力需求和验收标准。
- `design/` 负责目标态架构、接口契约和设计决策。
- `implementation/` 负责源码、脚本、运行资产、测试和当前进展。

风铃被定义为自有移动端主客户端；Telegram 如果保留，默认只作为可选外部通知或轻量集成工具；两者共享同一个本地 runtime。

## 最近完成

- [2026-03-17] 方法论产出模板 + 结构化实施指引：
  - **5 个产出模板**：`design/ontology/templates/` 下新建 acceptance-case、design-decision、change-points、regression-case、dod-checklist 模板文件，约束门控产出的格式一致性
  - **gate-checks.yaml template 字段**：为 6 个产出类门控（acceptance_case_exists/updated、design_decision_exists、regression_case_created、dod_checklist_complete、change_points_analyzed）添加 `template` 字段指向对应模板
  - **GateResult.template_path**：models.py 新增字段，gate_checker.py 从 check_def 提取并传递到所有 GateResult 返回
  - **门控失败模板引用**：context.py 和 check_gates.py 在门控未通过时显示 `📋 参考模板: ...` 提示
  - **implementation 阶段测试指引注入**：context.py 新增 `_build_testing_guidance()`，从 testing-methodology.yaml 读取测试策略并格式化为有序步骤指引，注入 agent system prompt
  - **engine.py summary 携带 template**：`get_feature_summary()` 的 gate dict 新增 `template` 字段
  - **全量单元测试**：325 个通过，零回归

- [2026-03-17] code_agent 预算耗尽 + ctx.get 异常双修复：
  - **根因 1（预算）**：`--max-budget-usd 0.50` 对大文件场景过低，Claude CLI 被截断后 JSON 无 `result` 字段（`subtype: error_max_budget_usd`），返回 42 chars "(Claude Code 无输出)"
  - **根因 2（ctx.get）**：`ctx.get("methodology_engine")` 在 `ToolContext` 中抛 `KeyError`（键不存在时），穿透到 `run_tool` 的 except，返回 63 chars 的错误消息，code_agent 实际未执行
  - **修复 1**：预算上限从 $0.50 提高到 $2.00
  - **修复 2**：`error_max_budget_usd` subtype 处理，返回有意义的预算耗尽错误提示
  - **修复 3**：`ctx.get()` 调用纳入 try/except 范围，KeyError 降级而非崩溃
  - **修复 4**：`run_tool` 和 `code_agent` 的 except 路径加 `log.error` 输出堆栈，便于排查
  - **端到端验证**：风铃 → gemini-3-flash → code_agent → Claude CLI 全链路正常（21.5s, 74 chars）
  - **模型切换**：主模型从 `deepseek/deepseek-v3.2` 切换到 `google/gemini-3-flash-preview`
  - **单元测试**：12 个 code_agent 测试全部通过；全量 325 通过
  - **修复 2**：新增 `error_max_budget_usd` subtype 处理，返回有意义的错误消息（预算耗尽、建议拆分任务）
  - **修复 3**：通用 error subtype 处理（`subtype.startswith("error")`）
  - **单元测试**：新增预算耗尽测试，共 12 个测试全部通过；全量 325 通过
  - **模型切换**：主模型从 `deepseek/deepseek-v3.2` 切换到 `google/gemini-3-flash-preview`

- [2026-03-17] code_agent 方法论文档层补齐 + CLI 方法论上下文注入：
  - **验收场景**：新建 `requirements/acceptance/core/code-agent-cli-001.json`（5 个场景：成功调用、超时处理、模型映射、方法论注入、无方法论时不附加）
  - **设计决策**：新建 `design/decisions/code-agent-claude-cli.md`（CLI subprocess 选型、OpenRouter proxy、--append-system-prompt 注入方法论、安全控制）
  - **架构文档**：更新 `design/architecture/system-overview.md`，追加 code_agent 调用链路和 OpenRouter Proxy 支撑服务描述
  - **设计索引**：更新 `design/decisions/README.md` 追加条目
  - **code_agent.py**：handle() 新增方法论上下文注入逻辑，通过 `ctx.get("methodology_engine")` + `build_methodology_context()` 构建状态文本，通过 `--append-system-prompt` 传递给 Claude CLI；engine 不存在或构建失败时静默降级
  - **单元测试**：新增 4 个方法论注入测试（有引擎注入、无引擎不附加、空字符串不附加、异常降级），共 11 个测试

- [2026-03-17] code_agent 改造为 Claude Code CLI 调用：
  - **proxy 服务**：新建 `implementation/services/openrouter-proxy/proxy.py`，模型名翻译 + SSE thinking block 过滤 + null 清理
  - **code_agent.py**：从进程内子代理改为 spawn `claude-internal -p` 进程，通过 OpenRouter proxy 调用 Claude 模型
  - 支持 sonnet（默认）/ haiku / opus 三种模型选择
  - 单次预算上限 $0.50，超时 5 分钟
  - **start.sh / stop.sh**：追加 proxy 服务管理（端口 9999）
  - **单元测试**：7 个测试全部通过（成功/超时/错误/CLI缺失/模型映射/非JSON输出/默认模型）
  - **文档更新**：SKILL.md、TOOLS.md、.env.example

- [2026-03-17] 方法论本体强制执行系统（Methodology Ontology Enforcement）— 4 个 Phase 全量交付：
  - **Phase 1: 本体定义 + 静态门控 CLI**
    - `requirements/methodology/enforcement.md` — 需求文档（验收标准 AC-1~AC-7）
    - `design/ontology/README.md` — O+G+P+f_θ 四层本体说明
    - `design/ontology/methodology.yaml` — 6 种 ChangeType 强制路径 + 门控规则
    - `design/ontology/gate-checks.yaml` — 6 个门控检查实现（fs_check / runtime）
    - `design/decisions/ontology-enforcement.md` — 设计决策记录
    - `implementation/runtime/methodology/models.py` — Pydantic 数据模型
    - `implementation/runtime/methodology/ontology.py` — YAML 加载 + 懒加载单例
    - `implementation/runtime/methodology/gate_checker.py` — 文件系统 / 命令执行门控检查
    - `implementation/runtime/methodology/cli.py` — 独立 CLI 工具（check / list-change-types / show-path）
  - **Phase 2: Neo4j 图谱 + Feature 生命周期**
    - `design/ontology/graph-schema.cypher` — Neo4j 节点 schema
    - `implementation/runtime/methodology/graph_ops.py` — Feature CRUD + 产物关联（降级模式）
    - `implementation/runtime/methodology/engine.py` — MethodologyEngine 状态机（create/advance/skip/complete）
    - `implementation/runtime/tools/skills/methodology/` — 4 个 Skill tools（create_feature/check_gates/advance_phase/link_artifact）
    - `implementation/runtime/task_graph/graph_store.py` — 追加 Feature 索引
  - **Phase 3: Agent 上下文注入 + 拦截器**
    - `implementation/runtime/methodology/context.py` — 方法论状态注入 system prompt
    - `implementation/runtime/methodology/interceptor.py` — Tool call hard block（IMPLEMENTATION_TOOLS 拦截）
    - `implementation/runtime/agent.py` — init_methodology()、上下文注入、拦截器调用（`METHODOLOGY_ENFORCEMENT=off` 可关闭）
    - `implementation/channels/fengling/server.py` — startup 调用 init_methodology + `/api/methodology/features`
  - **Phase 4: 证据层 + 审计 + ops 面板**
    - `implementation/runtime/methodology/evidence.py` — 证据收集（test_result/trace/file_change）
    - `implementation/runtime/methodology/audit.py` — EventBus 审计日志 JSONL
    - `implementation/channels/fengling/static/ops.html` — 新增"🏛 方法论"面板（Feature 列表、门控状态）
  - **全量测试**：288 个通过（新增 119 个方法论专项测试），零回归


  - **remind.py `date.today()` → CST 时区**：holiday/lunar/solar 三处 `date.today()` 改为 `datetime.now(_CST).date()`，与 CalendarChecker 保持一致，服务器非 CST 时区时不再返回错误日期
  - **notify.sh 静默时段用 CST 时区**：`date +%H` 改为 `TZ='Asia/Shanghai' date +%H`，UTC 服务器上不再错判静默窗口
  - **event_bus `_cron_task` 内层异常捕获**：`_cron_next_delay` 和 `publish` 各自加 try/except，cron 计算失败时等待 60s 后继续，publish 失败不中断循环
  - **server.py ops/status 预计算 next_trigger_date**：为每条日历提醒附加 `next_trigger_date`（提醒日）和 `next_event_date`（节日/目标日），调用 calendar_checker 的转换函数
  - **ops.html `_calNextDate` 优先用服务端日期**：检测 `entry.next_trigger_date` 字段，优先展示精确公历日期，holiday/lunar_date 现在也能显示"2026-09-10 09:00"
  - **ops.html `fetchData` 错误提示**：网络/解析失败时在页面显示"⚠️ 加载失败"而非静默失败；同时清理重复的 addEventListener
  - **`_write_calendar_reminder` 原子写**：先写 `.tmp` 临时文件再 `replace()`，防止写入中途崩溃导致 JSON 损坏丢失所有提醒
  - **全量单元测试**：169 个通过，零回归


  - **`my_schedule.py` `_conflict_warning` 字段安全访问**：与 remind.py 保持一致，改用 `.get()` 防 KeyError
  - **返回消息中已过期触发日提示**：holiday/lunar/solar 三处统一用 `_fmt_remind_date()` 格式化，`remind_date < today` 时显示"本周期触发日已过，将在下个周期触发"而非展示已过期日期
  - **全量单元测试**：169 个通过，零回归


  - **`_conflict_warning` 字段访问安全**：`e['datetime']` 等改为 `.get()` 防 KeyError
  - **cron 表达式本地预校验**：调用 Timer API 前先 `croniter.is_valid()` 校验，无效表达式提前返回友好错误
  - **CalendarChecker `today` 跨午夜一致性**：`today` 改为从 `_now_cst.date()` 派生，消除极端跨午夜情况下 `today` 与 `_now_cst` 日期不一致
  - **补充 upsert 测试**：新增 `test_upsert_preserves_last_notified_date` 和 `test_upsert_new_entry_has_no_last_notified` 两个单元测试，覆盖修改提醒时 `last_notified_date` 保留逻辑
  - **全量单元测试**：169 个通过（新增 2 个），零回归


  - **Bug 1（upsert 清零 last_notified_date 导致当天重复通知）**：覆盖时先找旧条目，将其 `last_notified_date` 保留到新 entry 中，防止修改提醒参数后当天重发
  - **Bug 2（旧 timers.json 无 session_key 字段）**：`restore_timers` 检测空 session_key 时记录 warning，提示用户重建该提醒
  - **Bug 3（once timer 重启后宽限窗口）**：过期判断从 `<= now` 改为 `<= now - 60`，60 秒内未送达的 timer 重启后立即补发
  - **Bug 4（advance_days 非数字字符串导致 ValueError 崩溃）**：用 try/except 包裹 `int()` 转换，非法值返回友好 error
  - **全量单元测试**：167 个通过，零回归


  - **Bug 1（CalendarChecker 深夜重启误触发）**：时间检查从「≥设定时间」改为「在触发时间 +120 分钟窗口内」；`_check_all` 提取 `_now_cst` 参数支持测试注入；修复对应单元测试
  - **Bug 2（croniter naive datetime 时区不一致）**：`remind.py` cron 分支 `get_next(datetime)` 返回 naive datetime，`.replace(tzinfo=_CST)` 补上时区，冲突检测不再抛 `TypeError`
  - **Bug 3（advance_days/time 校验误拦截 cron/delay）**：将校验从 handle 开头移入 holiday/lunar/solar 各自分支内部，cron/delay 类型不受影响
  - **Bug 4（notify 消息写入 chatHistory 导致刷新重放）**：SSE 通知 `addMsg` 改为 `save=false`，不持久化到 sessionStorage
  - **Bug 5（lunar/solar label 缺提前天数）**：lunar/solar 分支 label 生成统一加入提前天数后缀（与 holiday 对齐）
  - **全量单元测试**：167 个通过，零回归


  - **Bug 1（日历提醒无去重）**：`_write_calendar_reminder` 改为 upsert 语义，相同 type+标识符（holiday name / lunar month+day / solar month+day）覆盖而非追加，避免重复通知
  - **Bug 2（ops.html solar_date 不渲染）**：`renderCalendarReminders` 新增 `solar_date` 分支（☀️ 橙色标签）；`_calNextDate` 新增 solar_date 客户端日期计算，直接显示触发年月日
  - **Bug 3（SSE 通知以 AI 气泡呈现）**：新增 `.msg.notify` 样式（黄色暖色调，左侧金边）；SSE 消费改用 `addMsg('🔔 '+body, 'notify')`，视觉上明显区分于 AI 对话
  - **Bug 4（time_str 未校验）**：`handle()` 开头校验 `^([01]\d|2[0-3]):[0-5]\d$`，非法值直接返回 error
  - **Bug 5（advance_days 无上下界）**：校验 `0 ≤ advance_days ≤ 365`，负数或超大值返回 error
  - **Bug 6（_parse_delay 大写单位失败）**：将 `[smhd]` 改为 `[smhdSMHD]`（用 `s_lower` 处理，实际已覆盖），确保 "1H"/"30M" 正常解析
  - **Bug 7（_calNextDate 不显示年份）**：solar_date 分支计算今年/明年的精确触发日期并格式化为中文年月日；holiday/lunar_date 重新整理展示格式
  - **Bug 8（notify.py 截断 60→80 字）**：日志返回摘要从 60 字放宽到 80 字，agent 可看到更完整的消息
  - **全量单元测试**：167 个通过，零回归


  - **Bug 1（CalendarChecker 重启后错过当天提醒）**：`_loop()` 改为先立即调用 `_check_all()` 再进入睡眠循环
  - **Bug 2（Fengling session 提醒无法回到 Fengling）**：`remind.py` 向 Timer API POST 时带上 `session_key`；`_on_timer_fired` 新增 Fengling session 分支，`chat_id is None` 时转走 Web Push（SSE 广播到 Fengling UI）
  - **Bug 3（advance_days=0 显示"0天后"）**：`calendar_checker.py` 默认消息生成改为 `adv == 0 → "今天"` 逻辑
  - **Bug 4（remind tool description 缺少 solar 说明）**：description 新增 "solar" 参数说明，LLM 可识别公历年度日期
  - **Bug 5（advance_days/time 参数描述缺 solar）**：两个参数的 description 均补充 `/solar`
  - **Bug 6（CalendarChecker _loop 不处理 CancelledError）**：将 `asyncio.sleep` + `_check_all` 包裹在 `try/except`，`CancelledError` 单独 re-raise，其他 Exception 继续循环
  - **Bug 7（humanSeconds 显示"8760h 0m 0s"不友好）**：`ops.html` `humanSeconds()` 重写，分层显示：`<1min → xs`，`<1h → Xm Xs`，`<1d → Xh Xm`，`<30d → X天Yh`，更长 → 本地化日期
  - **全量单元测试**：167 个通过，零回归


  - **remind.py**：新增 `solar` 参数（格式 `M-D`）和 `_next_solar_for_solar()` 函数；`solar_date` 类型写入 `calendar_reminders.json`，支持 `advance_days` / `time`，与 `holiday`/`lunar` 完全对等
  - **calendar_checker.py**：`_matches_today()` 新增 `solar_date` 分支；新增 `_next_solar_date_for_solar()` 助手函数；通知消息默认文案完善
  - **需要4次 remind 调用覆盖全部情人节**：`solar="2-14"`（公历情人节）、`solar="3-14"`（白色情人节）、`holiday="七夕节"`（农历七夕）、`holiday="元宵节"`（农历元宵），均 `advance_days=3, time="21:00"`
  - **单元测试**：新建 `test_solar_reminder.py`，16个测试全部通过；全量单元测试 167 个通过
  - **TOOLS.md 更新**：remind 条目新增 solar 参数说明和示例

- [2026-03-16] 提醒/日程冲突检测（Conflict Detection）：
  - **remind.py 冲突检测**：新增 `_SCHEDULE_FILE`、`_load_schedule()`、`_parse_dt_simple()`、`_check_conflicts()`、`_conflict_warning()`；once（绝对/相对时间）和 cron 类提醒在成功后检测 ±60 分钟内已有日程，冲突时追加 `⚠️ 附近有日程安排` 段落；holiday/lunar 类跳过（天级粒度）
  - **my_schedule.py 冲突检测**：`action="add"` 写入成功后检测 ±30 分钟内已有日程，排除刚写入的事件本身（按 id 排除），冲突时追加冲突警告；操作不阻塞
  - **需求文档**：新建 `requirements/acceptance/core/reminder-conflict-001.json`（3 个验收场景）
  - **单元测试**：新建 `implementation/tests/unit/test_remind_conflicts.py`，11 个测试全部通过；全量单元测试 151 个通过
  - **TOOLS.md 更新**：remind 和 schedule add 条目均注明冲突提示行为
  - **intent 字段**：EventBus `schedule_timer()`/`schedule_cron()` 增加可选 `intent` 参数，持久化到 `timers.json`，恢复时读取；无 intent 时按 type 自动派生（向后兼容）
  - **Timer API 透传**：`bot.py` `_api_create_timer()` 接收并透传 `intent` 字段
  - **CalendarChecker**：新建 `implementation/runtime/calendar_checker.py`，每60分钟扫描 `calendar_reminders.json`，支持 `holiday`（7个内置农历节日）和 `lunar_date`（用户自定义）两种类型；`last_notified_date` 防重复；使用 `lunardate` 库做农历↔公历转换
  - **remind 工具扩展**：新增 `holiday`、`lunar`、`advance_days`、`time` 四个参数；农历/节日类提醒写入 `calendar_reminders.json`，返回下次触发公历日期
  - **fengling server 集成**：启动时初始化 CalendarChecker；`/api/ops/status` 增加 `calendar_reminders` 字段；新增 `DELETE /api/ops/calendar-reminders/{id}` 端点
  - **ops.html 升级**：timers 面板新增"语义意图"列（🔄周期/⏱一次性）；新增"日历提醒"子区域，展示 🏮节日 / 🌙农历 语义标签及取消按钮；概览面板增加"日历提醒"计数卡
  - **TOOLS.md 更新**：remind 工具文档增加 holiday/lunar/advance_days/time 参数说明
  - **需求文档**：新建 `requirements/acceptance/core/reminder-semantic-001.json`（3个验收场景）
  - **设计决策**：更新 `design/decisions/eventing-and-notification.md`，追加 CalendarChecker 设计、intent 字段结构、lunardate 选型说明
  - **单元测试**：新建 `test_calendar_checker.py`，7个测试全部通过；全量单元测试 140 个通过

- [2026-03-16] 提醒队列面板优化 + 周期提醒数据修复：
  - **ops.html 提醒队列**：新增"类型"列，`🔄 周期` 显示 cron 表达式/label，`⏱ 一次性` 区分显示
  - **数据修复**：删除 4 个重复的爬山 `once` timer（LLM 误用 delay 参数导致），改为 1 个 `cron="0 10 * * 0"` 周期任务（每周日 10:00）

- [2026-03-14] 进程管理 + 文档语义搜索（RAG）：
  - **process skill**：`process_start/list/log/kill/wait` 管理后台长时间进程，内存 registry + asyncio 流式日志采集
  - **docs skill**：基于 LlamaIndex + Qwen3 Embedding 的本地文档语义搜索，支持 PDF/TXT/MD/DOCX；增量索引持久化到 `runtime/data/docs_index/`；`docs_index/docs_search/docs_list` 三个工具
  - Embedding 接入：`http://langdata.models.qwen3-embedding-8b.polaris:8021/v1`，模型 `qwen3-8b-embedding-langdata`，可通过 env `DOCS_EMBED_*` 覆盖


  - **remind 持久化**：EventBus 增加 `persist_path` + `restore_timers()`，timer 落盘 `runtime/data/timers.json`；bot.py 启动时恢复未到期提醒
  - **记忆主动激活**：`chat_send` 第一轮自动调用 recall 并将结果注入 `[记忆检索]` system message；recall 失败静默忽略
  - **watchlist 订阅监控**：新增 watchlist skill（watch_add/watch_list/watch_remove）+ WatchlistChecker 后台检查器；server.py 启动时自动运行
  - **task_report 工具**：格式化任务树为中文摘要（✅进行中❌失败）；task skill 增加口语关键词；orchestrator 不可用时降级提示



## 当前状态

仓库已重组为 `requirements/`、`design/`、`implementation/` 三层：

- `requirements/` 负责产品需求、能力需求和验收标准。
- `design/` 负责目标态架构、接口契约和设计决策。
- `implementation/` 负责源码、脚本、运行资产、测试和当前进展。

风铃被定义为自有移动端主客户端；Telegram 如果保留，默认只作为可选外部通知或轻量集成工具；两者共享同一个本地 runtime。

## 最近完成

- [2026-03-13] coding skill（code_agent）：
  - 通过 Claude Code CLI（`claude-internal -p`）执行编码任务，经 OpenRouter proxy 调用 Claude 模型
  - 支持 sonnet/haiku/opus 模型选择，单次预算上限 $0.50
  - 关键词：写代码、实现、debug、修复、重构、代码 review 等


  - **删除** `kal.py`（khal 封装），日程统一使用 `schedule` 工具
  - **重写** `contacts.py`：从 khard CLI 改为直接读写 `implementation/data/contacts.yml`，新增 add/update action，生日查询改为本地计算
  - personal skill 现在完全本地化，无任何外部 CLI 依赖


  - `note` 追加到当日日志 `memory/YYYY-MM-DD.md`，带时间戳和可选分类
  - `remember` 追加到 `MEMORY.md` 长期记忆，支持指定章节
  - `recall` 全文搜索 MEMORY.md + 最近 30 天日志，AND 关键词匹配
  - 关键词覆盖：记住/记一下/备忘/笔记/别忘了/之前说过 等


  - **重构** `tools/__init__.py`：新增 `SkillDef` 数据结构、`discover_skills()`、`get_active_skills()`、`get_skill_context()`；`get_schemas(message)` 支持按关键词懒加载，兼容旧调用（`message=""`全量返回）
  - **新建** `tools/skills/` 目录，4 个 Skill 包：`system`（始终激活）、`personal`、`notification`、`task`，每包含 `SKILL.md`（YAML frontmatter + 操作规范）
  - **迁移** 所有工具文件（19个）到对应 Skill 子目录，工具内 `from tools import tool` 导入路径无需改动
  - **微改** `agent.py`：每轮 `get_schemas(_user_message)` 按需激活，同时通过 `get_skill_context()` 将激活 Skill 的规范注入 system prompt
  - **更新** `TOOLS.md`：按 Skill 分组重新描述
  - **已验证**：98 单元测试全部通过；全量 11 工具、任务关键词 6 工具（task 需 orchestrator）、日程关键词 9 工具

- [2026-03-13] Web Push 调试修复 + 对话流同步：
  - **修复** VAPID 私钥格式：PKCS8 PEM → raw 32字节 base64url，重新生成密钥
  - **修复** SW 版本缓存导致 postMessage 不触发：改为服务器端 SSE 广播（`/api/notify-stream`），彻底不依赖 SW 版本
  - **修复** `calendar.py` 文件名遮蔽标准库，rename → `kal.py`；`schedule.py` 同理 → `my_schedule.py`
  - **新增** `schedule` 工具（本地 JSON 日程存储，不依赖系统日历）+ `remind` 支持绝对时间
  - **新增** `agent.py` 每轮注入当前时间（CST），解决"周六几点"类请求 Too many tool rounds 问题
  - **新增** SOUL.md 日程行为规范：提醒类请求同时调 schedule add + remind
  - **已验证**：系统通知弹窗 + 对话气泡双渠道同步，Chrome 后台可收到，Edge/WNS 不兼容


  - **新增** `implementation/ops/scripts/gen_vapid.py`：VAPID 密钥生成（EC P-256 raw base64url 格式，pywebpush 兼容）
  - **新增** `implementation/channels/fengling/push_sender.py`：订阅持久化 + 并发推送 + 自动清理过期订阅
  - **新增** `implementation/channels/fengling/static/sw.js`：Service Worker
  - **新增** `implementation/channels/fengling/static/manifest.json`：PWA manifest
  - **修改** `server.py`：`/sw.js`、`/manifest.json` 路由 + `/api/push/*` 四个端点
  - **修改** `index.html`：🔕/🔔 订阅按钮 + iOS A2HS 提示 + push JS
  - **修改** `notify.py`：并发双渠道（Telegram + Web Push）
  - **修改** `bot.py`：定时器触发后 fire-and-forget Web Push
  - **修复** VAPID 密钥格式错误：原存 PKCS8 PEM，pywebpush 需要 raw 32字节 base64url，重新生成后推送正常
  - **已知限制**：Edge on Windows 使用 WNS，与 pywebpush VAPID 不兼容，需用 Chrome 订阅


  - **修复**：`conftest.py` 补充仓库根目录到 `sys.path`，单元测试从 93+1错误 → 98 全部通过
  - **修复**：`agent.py` 在 system prompt 最前面注入 `_IDENTITY_LOCK`，强制覆盖 Gemini/GPT 等底层模型的内置自我认知，确保 persona 始终表现为"希露菲"
  - **修复**：`SOUL.md` 安全章节补充"禁止透露底层 LLM 名称"约束
  - **新增 6 个工具**（`implementation/runtime/tools/`）：
    - `fetch_url` — 抓取 URL 内容，HTML 自动转纯文本
    - `list_files` — 目录浏览，支持递归
    - `calendar` — 读写日历（via khal）
    - `contacts` — 查询通讯录（via khard）
    - `remind` — 延时提醒（包装 Timer API，支持 '5m'/'2h'/'1d' 等人性化格式）
    - `notify` — 即时推送通知（包装 notify.sh，支持 urgent 静默时段绕过）
  - **更新** `TOOLS.md`：10 个工具的完整说明
  - 工具总数：5 → 10（含 task graph 工具注入后为 17）

- [2026-03-12] 工具执行沙箱 P0 落地（`design/decisions/tool-sandbox.md`）：
  - 新增 `runtime/tools/sandbox.py`：路径分区（安全区/受控区/禁区）+ 命令过滤（黑名单/警告）+ `check_permission()` 统一拦截
  - `tools/__init__.py` 的 `run_tool()` 增加沙箱前置检查
  - `exec.py`、`write_file.py` schema 增加 `confirmed` 可选参数支持阻塞式确认
  - 46 条单元测试全部通过（路径分类、命令过滤、读写权限、disabled 模式）
- [2026-03-12] 风铃主界面 markdown 渲染 + mermaid 支持：
  - AI 消息全面 markdown 渲染（marked.js 本地化，不依赖 CDN）
  - 流式阶段 500ms debounce 预览 markdown，完成后最终渲染 + 代码块复制按钮
  - Mermaid 图表按需加载（检测到 mermaid 代码块时才动态加载）
  - 暗色主题完整 markdown 样式（标题、列表、表格、代码、引用、链接等）
  - 设计决策更新：明确"对话即界面"原则，`/tasks` 等页面仅作开发调试入口
- [2026-03-12] 任务图 Web UI 重构：从 Cytoscape.js DAG 图切换为可折叠目录树视图
  - 移除 Cytoscape/dagre/cytoscape-dagre 三个 CDN 依赖
  - 纯 DOM 递归渲染树形结构，状态图标 + badge + 进度计数 + 焦点标记
  - 展开/折叠子树 + inline 详情面板（intent, next_action, result_summary, error_summary）
  - 默认展开规则：running/queued 自动展开，终态折叠，焦点及祖先强制展开
  - SSE 实时增量更新（已有节点 DOM 原地更新，新节点全量重载）
  - 视觉风格对齐风铃主界面暗色主题（CSS variables）
- [2026-03-12] 任务图（Task Graph）系统完整实现：
  - 需求层：`requirements/core/task-graph.md` 能力规格 + 2 个验收场景
  - 设计层：`design/decisions/task-graph-neo4j.md` Neo4j 选型 + `design/architecture/task-graph.md` 架构设计
  - 实现层 Phase 1：`implementation/runtime/task_graph/` 核心图引擎（models, graph_store, stack, orchestrator, tools, events），Neo4j Docker 容器配置，agent.py 集成（Context 注入 + 工具注册）
  - 实现层 Phase 2：Fengling REST API（6 个端点 + SSE 实时推送），Web UI（tasks.html/js/css）
  - 实现层 Phase 3：CLI 入口（list/tree/show/focus/cancel），启动恢复机制
  - 实现层 Phase 4：单元测试 + 集成测试，ops 脚本更新（start/stop/check），requirements.txt 更新
- [2026-03-09] 收敛渠道优先级：明确风铃是主客户端，Telegram 只作为可选外部集成 / 通知工具；同步更新 README、产品目标、架构决策、acceptance、tool choices 与 agent 上下文。
- [2026-03-09] 清理实现层测试表述：把 `implementation/tests/` 中残留的“主入口 / Web client”文案改成更中性的 channel/service 表达，避免把当前 transport 细节误写成产品层渠道定位。
- [2026-03-09] 纠正渠道定位理解：不再把风铃写成桌面主入口，而是定义为与 Telegram 并列的移动端用户渠道；同步更新 README、requirements、design、persona 指令与项目上下文文档。
- [2026-03-09] 补齐 requirements/acceptance/ 用例：`memory-recall-001`、`memory-correction-001`、`task-state-reporting-001`、`trust-boundary-002`、`cross-channel-delivery-001`；更新验收 README 索引。
- [2026-03-09] 新增 `design/architecture/session-identity.md`：定义 session_key 命名约定、V1 任务注册表格式（JSONL）、identity-map.yml 结构和跨渠道结果投递路径。
- [2026-03-09] 新增 `design/architecture/knowledge-gateway.md`：定义知识条目结构、从记忆层晋升触发条件、KnowledgeGateway 接口契约和 V1 实现约束。
- [2026-03-09] 补充 `design/architecture/runtime-core.md`：新增 Context Assembly 策略（组装顺序、token 预算分配、续作任务的上下文处理）。
- [2026-03-09] 新增 `design/architecture/policy-check.md`：定义委托边界数据格式（POLICY.md + DynamicGrant）、PolicyCheck 接口、TOOL_RISK_MAP 和审计记录约定。
- [2026-03-09] 新增 `design/evaluation/metrics-collection.md`：定义 audit.jsonl schema、北极星指标与核心体验指标的计算方式和 V1 采集路径。
- [2026-03-09] 新增 `design/evaluation/judge-rubrics.md` 中 `memory_utilization_v1` rubric。

- [2026-03-09] 新增 `design/decisions/ai-native-development-checklist.md`：把 AI 原生开发范式进一步落成默认执行清单，并接入根 README、设计索引、决策摘要、project context 与 AGENTS 指令。
- [2026-03-09] 新增 `design/decisions/ai-native-development.md`：把“文档/验收/评测先于实现、证据先于判断、失败样本资产化”的 AI 原生开发范式沉淀为项目级设计原则，并接入 README、决策索引和项目规则。
- [2026-03-09] 完成仓库三层重组：新增 `requirements/`、`design/`、`implementation/`，把需求、设计与实现从物理目录和文档语义上拆开。
- [2026-03-09] 新增 AI 原生测试组织：在 `requirements/acceptance/` 定义前置验收场景，在 `design/evaluation/` 定义评测协议和 rubric，在 `implementation/evals/` 增加 acceptance runner scaffold。
- [2026-03-09] 重写根目录导航与分层索引：`README.md`、`requirements/README.md`、`design/README.md`、`implementation/README.md`。
- [2026-03-09] 重写产品主叙事：明确多渠道共享同一 AI runtime，并围绕统一任务、记忆与知识资产组织产品。
- [2026-03-09] 将运行时代码、渠道实现、persona、数据、脚本和测试归入 `implementation/`，并保留根目录薄包装入口。
- [2026-03-09] 将架构、能力与服务文档拆分为需求层和设计层，减少“产品定义 / 架构设计 / 当前实现”混写。
- [2026-03-06] 自建 Agent Runtime：openai SDK 直连兼容 LLM 接口，内置 `exec` / `read_file` / `write_file` / `search` 四个工具，风铃与 Telegram 已统一接入。
- [2026-03-05] 事件驱动定时器架构落地：EventBus + Timer API 支撑异步提醒与主动回报。

## 进行中

- SearXNG 网络修复（容器内 HTTPS 出站仍不稳定）
- 工具沙箱 P1：Git auto-stash 兜底
- 记忆层与知识层的维护闭环

## 当前目录约定

| 目录 | 作用 |
|------|------|
| `requirements/` | 产品与能力需求 |
| `design/` | 目标态架构、接口与决策 |
| `implementation/runtime/` | 共享 runtime 核心 |
| `implementation/runtime/task_graph/` | 任务图系统（Neo4j DAG） |
| `implementation/channels/` | 风铃与 Telegram 渠道实现 |
| `implementation/services/` | 语音、搜索、Neo4j、OpenRouter proxy 等支撑服务 |
| `implementation/assets/persona/` | persona 与长期运行指令 |
| `implementation/data/` | 审计与结构化本地数据 |
| `implementation/ops/` | 启停、诊断、部署、辅助脚本 |
| `implementation/tests/` | 测试套件 |
| `implementation/evals/` | 验收评测运行器与报告 |

## 待确认

- 知识层的独立系统将以什么形式与 runtime 对接
