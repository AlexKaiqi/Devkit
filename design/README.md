# Design

`design/` 描述目标态系统如何被组织，不绑定当前代码形态。

## 边界

- 可以写：模块职责、交互关系、对象模型、接口协议、设计决策。
- 不写：当前完成度、运行命令、具体部署状态、一次性迁移细节。

## 目录

| 目录 | 说明 |
|------|------|
| [architecture/](architecture/) | 系统总览与关键子系统设计 |
| [interfaces/](interfaces/) | 事件、任务、工具等契约 |
| [decisions/](decisions/) | 仍然生效的设计决策 |
| [tooling/](tooling/) | 工具选型原则与取舍 |
| [service-map.md](service-map.md) | 设计上的服务职责映射 |

## 建议阅读顺序

1. [系统设计总览](architecture/system-overview.md)
2. [Runtime Core](architecture/runtime-core.md)
3. [风铃渠道设计](architecture/channel-fengling.md)
4. [模型适配层](architecture/model-adapter.md)
5. [数据与知识设计](architecture/data-knowledge.md)
6. [事件系统接口](interfaces/event-system.md)
