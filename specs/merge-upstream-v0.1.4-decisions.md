# Merge Upstream v0.1.4 — Decisions

## Summary

Merged `upstream/main` (v0.1.4) into `merge-upstream-v0.1.4`. All 7 conflict files resolved, 65 tests passing.

## Key Decisions

### 1. config/schema.py
- Kept both `AliasChoices` import (ours) and `to_camel` import (upstream)
- Kept our `HttpConfig` class for HTTP channel; switched `ChannelsConfig` base to upstream's `Base` class (camelCase alias support)
- Kept our `McpConfig` field on root `Config`
- Preserved all upstream new provider configs (GitHub Copilot, SiliconFlow, Custom)

### 2. agent/context.py
- Kept our customized identity prompt (with sticker instructions, memory notes)
- Dropped upstream's generic fallback instructions (redundant with our SOUL.md/AGENTS.md bootstrap files)

### 3. agent/tools/message.py
- Kept our sticker_id, reaction, message_id parameters
- Adopted upstream's broader media description ("images, audio, documents" instead of just "images")
- Kept our detailed delivery feedback (reaction/sticker/media counts)

### 4. session/manager.py
- Kept our turn-alignment fix (trim non-user messages from window start)
- Adopted upstream's `max_messages=500` default (was 75)
- Adopted upstream's cleaner metadata iteration pattern (`for k in (...)`)

### 5. agent/loop.py
- Merged upstream's `on_progress` callback into `_run_agent_loop` and `_process_message`
- Kept our SILENT marker detection/stripping, tool use summary persistence, sliding-window consolidation
- Added upstream's `_strip_think()` for `<think>` block removal
- Added upstream's `_tool_hint()` for progress display
- Kept our `start_mcp()` method name (upstream renamed to `_connect_mcp`)
- Kept our `try/finally` pattern for MCP cleanup in `process_direct`

### 6. channels/telegram.py
- Kept our structured send method with helper methods (_send_text, _send_sticker, _send_with_media, _resolve_reply_to_message_id)
- Added upstream's `_split_message()` for long message splitting into `_send_text`
- Added upstream's `_get_media_type()` for voice/audio/document detection into `_send_with_media`
- Preserved our SILENT handling, sticker support, reaction support, reply_to support
- Preserved upstream's sender_id/allowlist matching, inbound media handling (voice, audio, documents)

### 7. cli/commands.py
- Adopted upstream's full provider routing (OpenAI Codex OAuth, Custom provider, OAuth registry)
- Kept our `default_stream` config pass-through
- Kept our file-based logging setup; added upstream's cron service init
- Merged our `try/finally` MCP cleanup with upstream's `on_progress` callback
