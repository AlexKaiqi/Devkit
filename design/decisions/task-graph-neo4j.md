# 选型决策：Neo4j 作为任务图存储

> 状态：已采纳
> 日期：2026-03-12

## 背景

Devkit 需要一个持久化存储来承载任务图（DAG），支持任务之间的分解、依赖、续作等多种关系。当前任务状态只存在于内存中的聊天历史，进程重启即丢失。

## 候选方案

### 1. JSONL 文件（当前审计日志方案的扩展）

- 优点：零依赖，实现简单
- 缺点：无法高效查询图关系（路径、子树、拓扑排序），没有事务保证

### 2. SQLite + 邻接表

- 优点：轻量嵌入式，SQL 查询
- 缺点：图遍历需要递归 CTE，深度层级性能差，关系语义不自然

### 3. Neo4j

- 优点：
  - 原生图存储，Cypher 查询语言天然适合路径遍历、子树查询
  - 社区版免费，Docker 一键部署
  - async Python driver（neo4j-driver）成熟
  - 图可视化内置浏览器，调试友好
- 缺点：
  - 多一个容器依赖
  - 学习成本（Cypher 语法）

## 决策

选择 **Neo4j 5 Community Edition**。

理由：
1. 任务图的核心操作——栈路径遍历（沿 SUBTASK_OF 上溯）、子树查询、拓扑排序——全是图数据库的强项，Cypher 一条语句搞定，SQL 需要多层递归。
2. Docker 部署对现有架构冲击小（SearXNG 已有 Docker 容器先例）。
3. 社区版功能对当前规模完全够用。
4. 内置 Neo4j Browser 可作为调试工具，降低开发成本。

## 影响

- `docker-compose.yml` 新增 neo4j 服务
- `requirements.txt` 新增 `neo4j` Python driver
- `start.sh` / `stop.sh` / `check.sh` 需要加入 Neo4j 容器管理
- `.env` 新增 `NEO4J_URI`、`NEO4J_PASSWORD` 配置项
