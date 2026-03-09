# Knowledge Gateway 设计

本文档定义知识层的接口契约、知识条目数据结构、从记忆层晋升的触发条件，以及维护操作的接口。

## 设计定位

Knowledge Gateway 是 runtime 与知识层之间的唯一接入点。它对 runtime 屏蔽知识层的底层实现（文件、图数据库或外部服务），runtime 只通过本文档定义的接口读写知识。

知识层不等于记忆层。两者的核心区别：

| | 记忆层 | 知识层 |
|-|--------|--------|
| 写入成本 | 低，可自由追加 | 较高，需筛选和结构化 |
| 结构化程度 | 自由文本为主 | 有字段约束 |
| 维护方式 | 人工直接编辑 | 通过 Gateway 维护 |
| 生命周期 | 允许粗粒度过期 | 显式标记版本与有效性 |
| 复用方式 | 全量装入上下文 | 按场景按需召回 |

## 知识条目结构

```json
{
  "id": "knowledge-20260309-001",
  "type": "preference | fact | decision | entity | domain",
  "subject": "工作邮箱",
  "content": "kai@newcompany.com",
  "tags": ["联系方式", "邮件"],
  "source": {
    "origin": "user_provided | task_result | tool_query | document_extraction",
    "reference": "conversation-2026-03-09 / task-20260309-001",
    "confirmed": true
  },
  "validity": {
    "status": "active | deprecated | unverified",
    "created_at": "2026-03-09T10:00:00Z",
    "updated_at": "2026-03-09T10:00:00Z",
    "review_after": null
  },
  "supersedes": null
}
```

### 字段说明

| 字段 | 含义 |
|------|------|
| `type` | 知识类型：用户偏好、客观事实、技术决策、实体对象、领域知识 |
| `subject` | 知识主题，便于检索和去重 |
| `content` | 知识内容，可以是自由文本或结构化对象 |
| `source.origin` | 来源类型：用户明确提供 / 任务执行结果 / 工具查询 / 文档提炼 |
| `source.confirmed` | 是否经过用户或任务验证 |
| `validity.status` | `active`=当前有效；`deprecated`=已被新条目取代；`unverified`=待验证 |
| `supersedes` | 本条目取代的旧条目 ID |

## 从记忆层晋升到知识层

并非所有记忆都需要晋升。触发晋升的条件：

1. **多次复用**：同一事实在多个任务中被重复引用
2. **用户明确指示**：用户说"把这个记下来"/"以后都用这个"
3. **任务产出高价值结论**：任务执行后产生了稳定的、可复用的结论
4. **记忆纠错时**：旧条目被修正，应将新值升级为可追踪的知识条目

晋升流程：

```
记忆层 (MEMORY.md / daily logs)
  └─ 识别候选条目（人工 or Agent 触发）
      └─ 构造 KnowledgeEntry（填写 source、type、tags）
          └─ KnowledgeGateway.upsert()
              └─ 旧条目标记 deprecated，新条目设为 active
```

## Gateway 接口

### 查询 / 召回

```python
def query(
    tags: list[str] | None = None,
    subject: str | None = None,
    type: str | None = None,
    status: str = "active"
) -> list[KnowledgeEntry]:
    """按标签、主题或类型检索有效知识条目"""

def get(id: str) -> KnowledgeEntry | None:
    """按 ID 精确获取条目"""
```

### 写入 / 更新

```python
def upsert(entry: KnowledgeEntry) -> str:
    """
    写入或更新知识条目。
    若存在相同 subject + type 的 active 条目，将其标记为 deprecated，
    并将新条目的 supersedes 指向旧条目 ID。
    返回新条目 ID。
    """

def deprecate(id: str, reason: str) -> None:
    """将条目标记为 deprecated，保留历史但不再召回"""
```

### 维护操作

```python
def deduplicate(subject: str) -> list[str]:
    """
    找出相同 subject 下的重复 active 条目，返回冗余条目 ID 列表。
    不自动合并，由调用方决定如何处理。
    """

def list_unverified() -> list[KnowledgeEntry]:
    """列出所有 status=unverified 的条目，用于人工复查"""

def list_overdue_review() -> list[KnowledgeEntry]:
    """列出 review_after 已到期的条目"""
```

## 上下文召回策略

runtime 在组装上下文时调用知识层的方式：

1. **会话开始时**：按 `type=preference` 召回用户偏好类知识，注入 system prompt
2. **任务规划阶段**：按任务 `tags` 召回相关领域知识
3. **遇到相似问题时**：按 `subject` 模糊匹配已有结论，避免重复执行

召回结果按 `validity.updated_at` 倒序排列，只召回 `status=active` 的条目。

## V1 实现约束

- V1 用本地 JSON 文件 `implementation/data/knowledge.json` 存储知识条目（数组格式）
- 知识层实现允许后续替换为图数据库或外部服务，Gateway 接口保持稳定
- V1 不实现自动去重，只提供 `deduplicate()` 辅助接口供人工或 Agent 调用
- 知识条目文件应纳入 git 版本管理，以便审计和回滚

## 相关文档

- [data-knowledge.md](data-knowledge.md)
- [runtime-core.md](runtime-core.md)
- [记忆层与知识层需求](../../requirements/core/memory-knowledge.md)
- [memory-recall-001](../../requirements/acceptance/core/memory-recall-001.json)
- [memory-correction-001](../../requirements/acceptance/core/memory-correction-001.json)
