# 将 Upstream v0.1.4 合并到本地 Main

## 任务

将 `upstream/main`（HKUDS/nanobot v0.1.4）合并到本地分支 `merge-upstream-v0.1.4`（基于我们的 `main`）。

## 分支准备

- 当前分支：`merge-upstream-v0.1.4`（已从 `main` 创建）
- 目标分支：`upstream/main`（已完成 fetch）
- 执行：`git merge upstream/main` 开始合并

## 冲突文件（7 个）

1. `nanobot/agent/context.py`
2. `nanobot/agent/loop.py`
3. `nanobot/agent/tools/message.py`
4. `nanobot/channels/telegram.py`
5. `nanobot/cli/commands.py`
6. `nanobot/config/schema.py`
7. `nanobot/session/manager.py`

## 我们的本地特性（必须保留）

- **Sticker 支持**：Telegram 贴纸收发（`message.py`、`telegram.py`）
- **[SILENT] 标记**：抑制重复外发消息（`loop.py`、`telegram.py`）
- **媒体/图片支持**：通过 Telegram 和钉钉发送图片（`message.py`、`telegram.py`）
- **reply_to**：在 Telegram 中回复指定消息（`message.py`、`telegram.py`）
- **滑动窗口记忆整合**：上下文窗口管理（`context.py`）
- **入站消息收集缓冲**：对入站消息进行批处理（`context.py`、`loop.py`）
- **状态接口**：HTTP 通道的 GET /api/status（`cli/commands.py`）
- **Bot 消息过滤**：Discord 通道过滤
- **基于文件的日志**：故障排查日志
- **工具使用摘要持久化**：存储到会话历史
- **扩展思考/effort 支持**：模型配置
- **MCP 连接超时**：鲁棒性改进
- **LiteLLM 回退加固**：Provider 韧性（`providers/litellm_provider.py`）

## Upstream 新特性（必须保留）

- **GitHub Copilot OAuth 登录 + provider**（`cli/commands.py`、`config/schema.py`）
- **SiliconFlow provider**（`config/schema.py`）
- **自定义 provider（OpenAI 兼容）**（`config/schema.py`）
- **流式中间进度**（`loop.py`）
- **Telegram 媒体处理**（语音、音频、图片、文档）（`telegram.py`）
- **Telegram 长消息分片**（`telegram.py`）
- **Telegram sender_id / allowlist 匹配**（`telegram.py`）
- **会话作用域切换到 workspace + 迁移**（`session/manager.py`）
- **Slack 线程回复 + reaction**
- **Cron 时区改进**
- **OAuth provider 注册表系统**（`cli/commands.py`）

## 合并规则

1. **两侧特性共存**：保留所有本地特性和所有 upstream 特性。
2. **功能重复时**：如果双方实现了相似功能（例如 Telegram 媒体处理），对比设计后选更完整/更稳健的实现，同时确保我们的额外字段（sticker、reply_to）被保留。
3. **配置 schema**：合并 upstream 新增的所有 provider 配置，同时保留我们的自定义字段。
4. **Session manager**：保留 upstream 的 workspace 作用域会话 + 迁移能力，并确保与我们的滑动窗口方案兼容。

## 验证

解决全部冲突后：

1. 运行测试：`cd /Users/jing1/Developer/github/nanobot && python -m pytest tests/ -v`
2. 检查 CLI：`cd /Users/jing1/Developer/github/nanobot && python -m nanobot --help`
3. 检查导入：`cd /Users/jing1/Developer/github/nanobot && python -c "from nanobot.agent.context import AgentContext; print('OK')"`
4. 检查导入：`cd /Users/jing1/Developer/github/nanobot && python -c "from nanobot.channels.telegram import TelegramChannel; print('OK')"`
5. 检查导入：`cd /Users/jing1/Developer/github/nanobot && python -c "from nanobot.session.manager import SessionManager; print('OK')"`

## 输出

合并完成后：
1. 使用以下提交信息提交：`merge: upstream/main v0.1.4 with local features preserved`
2. 将关键决策摘要写入 `specs/merge-upstream-v0.1.4-decisions.md`
