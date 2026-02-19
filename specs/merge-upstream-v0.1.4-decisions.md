# 合并 Upstream v0.1.4 - 决策记录

## 摘要

已将 `upstream/main`（v0.1.4）合并到 `merge-upstream-v0.1.4`。7 个冲突文件均已解决，65 项测试通过。

## 关键决策

### 1. config/schema.py
- 同时保留了 `AliasChoices` 导入（我们的）和 `to_camel` 导入（upstream）。
- 保留了我们用于 HTTP 通道的 `HttpConfig` 类；同时将 `ChannelsConfig` 的基类切换为 upstream 的 `Base`（支持 camelCase alias）。
- 在根级 `Config` 上保留了我们的 `McpConfig` 字段。
- 保留了 upstream 新增的所有 provider 配置（GitHub Copilot、SiliconFlow、Custom）。

### 2. agent/context.py
- 保留了我们自定义的身份提示词（包含贴纸指令、记忆说明）。
- 移除了 upstream 的通用兜底指令（与我们的 `SOUL.md`/`AGENTS.md` 启动文件功能重复）。

### 3. agent/tools/message.py
- 保留了我们的 `sticker_id`、`reaction`、`message_id` 参数。
- 采用了 upstream 更宽泛的媒体描述（"images, audio, documents"，而非仅 "images"）。
- 保留了我们更详细的投递反馈（reaction/sticker/media 计数）。

### 4. session/manager.py
- 保留了我们的轮次对齐修复（从窗口开头裁掉非用户消息）。
- 采用了 upstream 的 `max_messages=500` 默认值（原来是 75）。
- 采用了 upstream 更简洁的 metadata 迭代写法（`for k in (...)`）。

### 5. agent/loop.py
- 将 upstream 的 `on_progress` 回调合并到 `_run_agent_loop` 和 `_process_message`。
- 保留了我们的 SILENT 标记检测/剥离、工具使用摘要持久化、滑动窗口整合。
- 新增了 upstream 的 `_strip_think()`，用于移除 `<think>` 块。
- 新增了 upstream 的 `_tool_hint()`，用于进度展示。
- 保留了我们的 `start_mcp()` 方法名（upstream 改名为 `_connect_mcp`）。
- 在 `process_direct` 中保留了我们的 MCP 清理 `try/finally` 模式。
- **策略调整**：保留 upstream 的 `_bus_progress` fallback（`on_progress=None` 时仍发布中间进度），并将“是否对用户可见”的控制下沉到 channel 发送层处理。

### 6. channels/telegram.py
- 保留了我们结构化的发送方法及辅助方法（`_send_text`、`_send_sticker`、`_send_with_media`、`_resolve_reply_to_message_id`）。
- 将 upstream 的长消息分片 `_split_message()` 合入 `_send_text`。
- 将 upstream 的媒体类型检测 `_get_media_type()`（语音/音频/文档）合入 `_send_with_media`。
- 保留了我们的 SILENT 处理、sticker 支持、reaction 支持、reply_to 支持。
- 保留了 upstream 的 sender_id/allowlist 匹配与入站媒体处理（语音、音频、文档）。
- 新增渠道侧 progress notice 过滤：当 `metadata` 标记为进度消息时，Telegram 直接丢弃，不对终端用户外发中间进度文本。

### 6.1 channels/dingtalk.py / channels/discord.py
- 与 Telegram 对齐，DingTalk 和 Discord 在发送层同样丢弃 `metadata` 标记的 progress notice，避免中间工具调用提示刷屏。

### 7. cli/commands.py
- 采用了 upstream 的完整 provider 路由（OpenAI Codex OAuth、Custom provider、OAuth 注册表）。
- 保留了我们的 `default_stream` 配置透传。
- 保留了我们的文件日志初始化，并加入 upstream 的 cron 服务初始化。
- 将我们的 MCP 清理 `try/finally` 与 upstream 的 `on_progress` 回调完成合并。
