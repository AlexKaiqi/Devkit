# 项目进度

> 最后更新：2026-03-05

## 当前状态

双渠道对话已上线：风铃（语音网页端）+ Telegram Bot（文字+语音+图片+视频）。支持视觉理解（图片/视频帧），回复区分文本与附件。

## 进行中
- Google Calendar (vdirsyncer) 配置
- Home Assistant 连接配置

## 已完成

- [2026-03-05] TTS 引擎升级至豆包语音合成大模型，默认音色「甜美小源」，前端音色列表替换为 25 个大模型音色
- [2026-03-05] 图片/视频输入支持：风铃(上传/粘贴/拖拽) + Telegram(发图/发视频)，视频自动抽帧，VISION_MODEL 独立配置
- [2026-03-05] 回复内容区分文本/附件：对话文字朗读，代码块独立渲染（风铃显示代码框+复制按钮，Telegram 发独立消息）
- [2026-03-05] Telegram Bot 上线（文字+语音对话，豆包 STT/TTS，审计日志）
- [2026-03-05] 语音网页客户端命名为「风铃」，TTS 切换为豆包（34 音色），新增审计日志 + 逐句流式 TTS
- [2026-03-05] 风铃（语音对话）服务上线（push-to-talk + LLM 流式回复 + 自动朗读）
- [2026-03-05] STT 代理支持 webm 格式（浏览器录音通过 ffmpeg 转 PCM，送豆包 ASR）
- [2026-03-05] cloudflared 安装、Android 模拟器环境搭建（SDK + AVD + system image 手动下载）
- [2026-03-05] OpenCami → Gateway 设备配对 + token 认证配置完成，adb reverse 端口转发方案验证通过
- [2026-03-05] 虚拟手机（Android 15 / Pixel 7）通过 adb reverse 访问 OpenCami 聊天界面成功
- [2026-03-05] AI 分身结构性修复：记忆系统 + 技能矩阵更新 + HEARTBEAT 巡检 + Telegram 通知 + 结构化数据层 + 多项目支持
- [2026-03-05] AI 原生项目改造：Cursor Rules（project-context + onboarding + multi-agent 升级）、check.sh 诊断脚本、GOALS.md 填充、docker-compose 整合 SearXNG
- [2026-03-05] 外部工具链安装：himalaya / peekaboo / playwright / SearXNG / rclone / pandoc / paperscout / papis / khard 等
- [2026-03-05] .venv 升级至 Python 3.12（原 3.9.6 版本过旧）
- [2026-03-05] SearXNG 搜索引擎部署（Docker，集成到 start.sh / stop.sh）
- [2026-03-05] himalaya 邮件配置完成（Gmail App Password，IMAP/SMTP 已通）
- [2026-03-05] CAPABILITIES.md 扩展：新增科研/智能家居/人际管理/App操作等章节，增加第十章推荐工具清单
- [2026-03-05] openclaw/TOOLS.md 更新：允许新增工具命令
- [2026-03-05] .env.example 更新：新增 SearXNG / HASS / Telegram / Peekaboo 配置项
- [2026-03-05] setup.sh 更新：新增 Homebrew/pip 工具安装、Docker 检查、Python 3.12 支持
- [2026-03-05] README.md 更新：架构图新增外部工具链、前置条件加 Docker、服务列表加 SearXNG
- [2026-03-04] AI 分身更名：Kite → 希露菲，人设调整为混合风（平时温柔，做事干练）
- [2026-03-04] 去 Gemini 绑定：所有文档中 Gemini 硬编码改为模型无关表述

## 待确认

- Google Calendar 是否改用 gcalcli 替代 khal+vdirsyncer（OAuth 更简单）
