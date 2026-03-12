# implementation/runtime/ 目录 Python 代码结构分析报告

## 1. 概要
- **文件总数**: 11
- **总代码行数**: 1828 行

---

## 2. 文件统计与结构详细信息

### 1) `implementation/runtime/task_graph/graph_store.py`
- **代码行数**: 317 行 (占比 **17.34%**)
- **包含类 (Classes)**: `GraphStore`
- **包含函数 (Functions)**: `__init__`, `connect`, `close`, `_ensure_indexes`, `create_task`, `get_task`, `update_task`, `delete_task`, `add_subtask_edge`, `add_depends_on_edge`, `add_continuation_edge`, `get_stack_path`, `get_children`, `get_subtree`, `get_session_root_tasks`, `get_focus_task`, `check_siblings_all_completed`, `get_all_non_terminal_tasks`, `get_session_task_counts`, `get_parent`

### 2) `implementation/runtime/task_graph/orchestrator.py`
- **代码行数**: 269 行 (占比 **14.72%**)
- **包含类 (Classes)**: `TaskOrchestrator`
- **包含函数 (Functions)**: `__init__`, `_publish`, `create_task`, `decompose_task`, `complete_task`, `fail_task`, `update_task`, `get_task_status`, `build_context`, `recover_on_startup`, `_propagate_completion`, `_cascade_cancel`

### 3) `implementation/runtime/agent.py`
- **代码行数**: 268 行 (占比 **14.66%**)
- **包含类 (Classes)**: `AgentBackend`, `LocalAgent`
- **包含函数 (Functions)**: `resolve_session`, `chat_send`, `__init__`, `init_task_graph`, `_load_system_prompt`, `_get_session`, `_trim_session`, `resolve_session`, `chat_send`, `_tg_handler`

### 4) `implementation/runtime/task_graph/tools.py`
- **代码行数**: 241 行 (占比 **13.18%**)
- **包含类 (Classes)**: *(无)*
- **包含函数 (Functions)**: `handle_create_task`, `handle_decompose_task`, `handle_complete_task`, `handle_fail_task`, `handle_get_task_status`, `handle_update_task`

### 5) `implementation/runtime/tools.py`
- **代码行数**: 197 行 (占比 **10.78%**)
- **包含类 (Classes)**: *(无)*
- **包含函数 (Functions)**: `_exec`, `_read_file`, `_write_file`, `_search`, `register_task_graph_tools`, `run_tool`

### 6) `implementation/runtime/task_graph/cli.py`
- **代码行数**: 153 行 (占比 **8.37%**)
- **包含类 (Classes)**: *(无)*
- **包含函数 (Functions)**: `cmd_list`, `cmd_tree`, `_print_tree`, `cmd_show`, `cmd_focus`, `cmd_cancel`, `main`

### 7) `implementation/runtime/event_bus.py`
- **代码行数**: 137 行 (占比 **7.49%**)
- **包含类 (Classes)**: `Event`, `EventBus`
- **包含函数 (Functions)**: `__init__`, `subscribe`, `unsubscribe`, `publish`, `_safe_call`, `schedule_timer`, `_timer_task`, `cancel_timer`, `list_timers`, `shutdown`

### 8) `implementation/runtime/task_graph/models.py`
- **代码行数**: 123 行 (占比 **6.73%**)
- **包含类 (Classes)**: `TaskState`, `TaskNode`, `TaskStack`, `SessionTaskSummary`
- **包含函数 (Functions)**: `to_neo4j_props`, `from_neo4j_record`, `root`, `depth`

### 9) `implementation/runtime/task_graph/stack.py`
- **代码行数**: 91 行 (占比 **4.98%**)
- **包含类 (Classes)**: *(无)*
- **包含函数 (Functions)**: `render_stack_path`, `render_focus_details`, `render_session_summary`, `render_task_context`

### 10) `implementation/runtime/task_graph/events.py`
- **代码行数**: 28 行 (占比 **1.53%**)
- **包含类 (Classes)**: *(无)*
- **包含函数 (Functions)**: `task_event_payload`

### 11) `implementation/runtime/task_graph/__init__.py`
- **代码行数**: 4 行 (占比 **0.22%**)
- **包含类 (Classes)**: *(无)*
- **包含函数 (Functions)**: *(无)*