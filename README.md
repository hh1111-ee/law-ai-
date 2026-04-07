AI法律平台（演示版）

给竞赛评审的技术说明（摘要）
----
本项目展示了一个以实用工程化为目标的 AI 驱动法律咨询与社区系统，强调“可观测性、可靠性与工程实践”。与典型演示性仓库不同，我们把 Postgres 作为唯一权威存储（DB_ONLY），并在消息持久化与可用性上做了可验证的工程设计。

关键技术亮点（面向评审）
----
- 持久化与一致性：以 Postgres 为唯一权威（通过 `postgres_data` 适配层），移除本地 pickle 回退；保证单一数据源便于一致性与审计。
- 消息可靠性：在 DB 写入失败时，`MessageRetryManager` 将消息追加到 JSONL 文件并后台重试，避免消息丢失；这一设计易于验证（演示时可断开 DB 并观察 JSONL 行为）。
- 工程兼容性：考虑 Windows 平台异步驱动差异，不在模块导入阶段设置全局事件循环策略，而在程序入口使用 `loop_factory`，提高跨平台稳定性。
- 可观测性：详尽日志（文件与控制台）、健康检查 `/health/db`、启动时种子检查，便于评审快速确认系统健康与数据完整性。
- 渐进式迁移路径：保留清晰的 pickles -> Postgres 的迁移脚本模板（`scripts/migrate_pickles.py`），支持评审时展示从原型到工程化的演进。

系统架构（组件与职责）
----

```mermaid
graph TD
	Browser[前端 (静态 HTML/JS)] -->|REST / WebSocket| API[FastAPI 后端]
	API -->|持久化| Postgres[(Postgres DB)]
	API -->|失败时持久化| Retry[MessageRetryManager (JSONL)]
	API -->|可选：模型服务| Model[模型服务 (Ollama / 本地)]
```

- 前端：静态页面（`html/` 下），演示用无框架实现，重点在可读可测的交互逻辑（见 `html/私聊界面.html` 与 `html/js/app_config.js`）。
- 后端：主应用在 [聊天和用户后端/Combined_server.py](聊天和用户后端/Combined_server.py)，包含 REST 与 WebSocket，实现认证（演示级）、消息编排、帖子与评论管理。
- 存储：通过 [postgres_data/adapter.py](postgres_data/adapter.py) 封装 DB 操作，便于未来替换或增强（如引入事务、审计表、分片等）。
- 重试队列：`message_retry.py` 负责在 DB 不可用时把消息写入磁盘（JSONL），并在后台安全重试，支持死信文件与重试参数配置。

关键模块详解
----

- `聊天和用户后端/Combined_server.py`：主进程生命周期由 FastAPI 的 `lifespan` 管理，启动时进行 Postgres 种子检查、启动重试管理器，关闭时优雅释放资源。实现要点：DB_ONLY 强制检查、兼容 GET/POST 的私聊接口、WebSocket 长连接处理。
- `postgres_data/adapter.py`：异步 SQLAlchemy/asyncpg 适配层，暴露 CRUD、消息/用户查询与写入接口；包含同步 _sync 辅助以便脚本或特殊场景使用。
- `message_retry.py`：可配置的 JSONL 持久化重试队列；设计上与外部消息系统（Redis/Kafka）接口相似，便于迁移到集中式队列。
- `ChatMessage.py` 与 `user.py`/`post.py`：保留的内存管理与旧有 Pickle 保存逻辑已逐步退役；必要的保存/加载方法被改为惰性导入 `pickle`，以避免模块加载时强依赖本地文件。

可靠性与容错设计
----

- DB_ONLY：服务在启动阶段强制要求 Postgres 可用（并执行种子检查），避免启动后依赖本地回退造成数据不一致。
- 消息写入路径：正常情况下直接写入 Postgres；若写入抛出异常则把消息交由 `MessageRetryManager` 持久化并异步重试，保证“至少一次”投递到持久化层。
- 启停流程：`lifespan` 中启动/停止重试管理器，退出时跳过本地 pkl 写回以避免与 DB 冲突或丢失主权数据源。

并发、兼容性与性能考量
----

- 并发模型：使用 uvicorn + FastAPI 的异步模型；对于本地模型调用（阻塞）通过线程池隔离，并发量受 `MODEL_CONCURRENCY` 控制（默认 2）。
- 连接池与 DB：建议在生产部署时正确配置 asyncpg 的连接池大小以匹配 uvicorn worker 数量与请求并发。
- Windows 兼容：避免在模块顶层设置 `set_event_loop_policy`；入口使用 `asyncio.Runner(loop_factory=asyncio.SelectorEventLoop)` 或 `asyncio.run(..., loop_factory=...)`，确保 asyncpg/psycopg 在 Windows 上稳定运行。

安全性说明（演示级与推荐改进）
----

- 当前演示实现：演示用密码字段与可选的 `passlib[argon2]` 支持；认证/授权为演示级，请勿直接用于生产。
- 推荐改进：使用 JWT + HTTPS、引入速率限制、输入校验（pydantic 严格模式）、数据库层加密与审计链、密钥/机密管理（Vault/KMS）。

可扩展性与部署建议
----

- 小规模演示：单机 uvicorn，可通过 `uvicorn "聊天和用户后端.Combined_server:app" --workers 1 --port 8000` 启动。
- 生产建议：容器化（Docker）+ Kubernetes 部署，多副本后端 + 共享 Postgres，外部化重试队列（Redis/Kafka），并使用 Stateful/流式迁移策略将 JSONL 重试队列过渡到中心化队列。

评估指标与演示路线（给评审）
----

建议的现场演示步骤（5–10 分钟）：

1. 启动 Postgres 与后端服务，打开私聊页面（`html/私聊界面.html`）。
2. 正常发送私聊消息，展示消息写入到 DB（观察日志、或查询 `postgres` 表）。
3. 模拟故障：临时停掉 Postgres，继续发送多个私聊消息，展示如何在 `pending_messages.jsonl` 中看到持久化的消息行（位于 `数据库/` 下）。
4. 恢复 Postgres，观察后台重试任务将消息入库并完成投递；演示日志中关于重试的可观测条目。

评审关注点（可供问答）
- 为什么选择 JSONL 重试而非直接使用 Redis/Kafka？（答案：实现简单、可现场演示、易于验证持久性；生产环境建议切换到集中式队列）
- 如何证明消息“不丢失”？（演示中通过停止 DB、发消息、恢复 DB 来展示文件持久化与重试入库流程）
- 扩展到高并发场景的关键瓶颈是什么？（DB 连接池、WebSocket 数量、模型并发调用）

如何运行（快速上手）
----

PowerShell 快速运行示例：

```powershell
& d:\项目：ai法律平台\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn "聊天和用户后端.Combined_server:app" --host 0.0.0.0 --port 8000
```

运行测试：

```powershell
python -m pytest -q tests/test_message_retry.py
```

开发者与维护信息
----

- 关键文件：
	- [聊天和用户后端/Combined_server.py](聊天和用户后端/Combined_server.py)
	- [postgres_data/adapter.py](postgres_data/adapter.py)
	- [message_retry.py](message_retry.py)
	- [html/私聊界面.html](html/私聊界面.html)
	- [html/js/app_config.js](html/js/app_config.js)
- `scripts/migrate_pickles.py` 提供了将旧 Pickle 数据迁移到 Postgres 的参考脚本（演示迁移策略）。

开发环境与 Playwright 修复指南
----

本项目在 Windows 环境下的开发与演示测试有一些平台依赖需要说明，尤其是 Playwright 浏览器二进制的版本管理。下面是合并自 `CLAUDE.md` 的关键要点与可执行修复脚本。

- 操作系统与环境：Windows 10，建议使用 Git Bash 或 PowerShell 开发；文件系统为不区分大小写，行结束为 CRLF。
- 问题场景（常见）：Playwright 在升级后可能期望一个不同的 Chromium 版本目录（如 `chromium-1200`），本地已有的版本目录为 `chromium-1181`，导致报错 “Executable doesn't exist at chromium-XXXX”。

一键安装 / 修复脚本（Windows PowerShell）
----

脚本位置：`scripts/install_playwright.ps1`

用途：检查 `npx` 可用性、下载 Playwright 的 Chromium 浏览器，并在需要时尝试创建本地符号链接以兼容版本目录差异。

使用（以管理员身份运行以允许创建符号链接）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_playwright.ps1
```

脚本要点（执行逻辑）：
- 检查 `npx` 是否可用，并提示安装 Node.js/npm（如找不到则中断）。
- 执行 `npx playwright@latest install chromium` 下载 Chromium 二进制。
- 若 Playwright 下载后仍提示目录不匹配，脚本会检测 `%%LOCALAPPDATA%%\ms-playwright` 中的目录，并（在管理员模式下）使用 `cmd /c "mklink /J chromium-1200 chromium-1181"` 创建目录联接以兼容旧版本路径。

管理员提示与注意事项
----

- 创建目录联接 (`mklink /J`) 需要管理员权限。脚本会检测当前进程是否为管理员，并在非管理员时给出明确提示并显示需要运行的命令。
- 若组织策略禁止创建联接，请联系管理员或手动把目标目录复制为所需名称（耗时且占用磁盘）。
- Playwright 的浏览器文件较大（数百 MB），请保证网络与磁盘空间充足。

故障排查快速命令
----

以下命令可用于手工排查或在无法运行脚本时手动修复：

```powershell
# 下载 Chromium
npx playwright@latest install chromium

# 手动创建符号链接（需管理员 cmd）
cd %LOCALAPPDATA%\ms-playwright
cmd /c "mklink /J chromium-1200 chromium-1181"
```

保留与合并说明
----

原 `CLAUDE.md` 已作为开发环境笔记保留在仓库中，可按需重命名为 `DEV_ENV.md` 或合并至 README。本次已将其 Playwright 指南核心合并到本节，并新增脚本 `scripts/install_playwright.ps1` 供演示与开发使用。

已知局限与后续工作（评审时可讨论）
----

- 当前演示仍依赖明文或演示级别的认证；生产需替换为成熟认证授权方案。
- 将 JSONL 重试队列迁移到 Redis/Kafka 是下一步关键工程改进，以满足大规模并发与监控需求。
- 需要进行系统级压力测试、索引优化与查询性能调优以支持大规模用户。

附录：环境变量与配置（摘要）
----

- `DB_ONLY`：是否仅使用数据库作为持久化（默认启用）。
- 消息重试相关变量（可通过环境变量覆盖）：
	- `MSG_RETRY_FILE`（默认 `数据库/pending_messages.jsonl`）
	- `MSG_RETRY_INTERVAL`（重试周期，秒）
	- `MSG_RETRY_MAX_RETRIES`（单条消息最大重试次数）

结语
----

 

---


