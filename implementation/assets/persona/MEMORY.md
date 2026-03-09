# 长期记忆

> 希露菲的持久知识库。每次会话开始时读取，发现新的重要信息时追加。
> 不要覆盖旧条目，只做增量添加。

## 用户偏好

- 工具选型偏好：开源优先、CLI 优先、闭源仅限不可替代
- 沟通语言：中文为主，技术术语保留英文
- 汇报风格：结构化、简洁、关注结果不关注过程
- Python 版本：项目使用 3.12（.venv），不用系统自带 3.9
- 邮箱：alexkaiqi@gmail.com（himalaya 已配通 Gmail App Password）

## 经验教训

- himalaya 配置：encryption 字段要用 `backend.encryption.type = "tls"` 而非 `backend.encryption = "tls"`
- brew install 多个包时如果某个卡住（如 python@3.14 下载），会阻塞整个命令，需要单独 kill
- .venv 从 Python 3.9 升级到 3.12 需要重建：删除旧 .venv，用 python3.12 -m venv 创建新的，再装所有依赖
- paperscout 有未声明的依赖：需要额外 pip install arxivy dblpcli s2cli
- Gmail IMAP 在某些网络环境下连接不稳定（TLS handshake EOF），多试几次通常能通

## 重要背景

- 项目 Devkit：AI 分身平台，通过 LocalAgent + Cursor CLI 调度
- AI 分身名字：希露菲（无职转生角色），性格温柔+干练
- 当前主路径：风铃主入口 + Telegram 次入口 + 共享 LocalAgent runtime
- 服务架构：SearXNG(:8080) + STT(:8787) + 风铃(:3001) + Timer API(:8789)
- SearXNG 通过 docker-compose.yml 管理，settings.yml 启用 JSON API
