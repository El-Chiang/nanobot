# Merge Upstream v0.1.4 into Local Main

## Task

Merge `upstream/main` (HKUDS/nanobot v0.1.4) into local branch `merge-upstream-v0.1.4` (based on our `main`).

## Branch Setup

- Current branch: `merge-upstream-v0.1.4` (already created from `main`)
- Target: `upstream/main` (already fetched)
- Run: `git merge upstream/main` to start

## Conflict Files (7)

1. `nanobot/agent/context.py`
2. `nanobot/agent/loop.py`
3. `nanobot/agent/tools/message.py`
4. `nanobot/channels/telegram.py`
5. `nanobot/cli/commands.py`
6. `nanobot/config/schema.py`
7. `nanobot/session/manager.py`

## Our Local Features (MUST preserve)

- **Sticker support**: send/receive Telegram stickers (`message.py`, `telegram.py`)
- **[SILENT] marker**: suppress duplicate outbound messages (`loop.py`, `telegram.py`)
- **Media/image support**: send images via Telegram and DingTalk (`message.py`, `telegram.py`)
- **reply_to**: reply to specific messages in Telegram (`message.py`, `telegram.py`)
- **Sliding-window memory consolidation**: context window management (`context.py`)
- **Inbound message collect buffer**: batching incoming messages (`context.py`, `loop.py`)
- **Status endpoint**: GET /api/status for HTTP channel (`cli/commands.py`)
- **Bot message filtering**: Discord channel filtering
- **File-based logging**: troubleshooting logs
- **Tool use summary persistence**: store in session history
- **Extended thinking/effort support**: model config
- **MCP connection timeout**: robustness improvement
- **LiteLLM fallback hardening**: provider resilience (`providers/litellm_provider.py`)

## Upstream New Features (MUST preserve)

- **GitHub Copilot OAuth login + provider** (`cli/commands.py`, `config/schema.py`)
- **SiliconFlow provider** (`config/schema.py`)
- **Custom provider (OpenAI compatible)** (`config/schema.py`)
- **Stream intermediate progress** (`loop.py`)
- **Telegram media handling** (voice, audio, images, documents) (`telegram.py`)
- **Telegram message length splitting** (`telegram.py`)
- **Telegram sender_id / allowlist matching** (`telegram.py`)
- **Session scope to workspace + migration** (`session/manager.py`)
- **Slack thread reply + reaction**
- **Cron timezone improvements**
- **OAuth provider registry system** (`cli/commands.py`)

## Merge Rules

1. **Both features coexist**: Keep ALL local features AND all upstream features
2. **Duplicate functionality**: If both sides implement similar features (e.g., Telegram media handling), compare designs and pick the more complete/robust one, then ensure our extra fields (sticker, reply_to) are preserved
3. **Config schema**: Merge all new provider configs from upstream while keeping our custom fields
4. **Session manager**: Keep upstream's workspace-scoped sessions + migration, ensure compatibility with our sliding-window approach

## Validation

After resolving all conflicts:

1. Run tests: `cd /Users/jing1/Developer/github/nanobot && python -m pytest tests/ -v`
2. Check CLI: `cd /Users/jing1/Developer/github/nanobot && python -m nanobot --help`
3. Check import: `cd /Users/jing1/Developer/github/nanobot && python -c "from nanobot.agent.context import AgentContext; print('OK')"`
4. Check import: `cd /Users/jing1/Developer/github/nanobot && python -c "from nanobot.channels.telegram import TelegramChannel; print('OK')"`
5. Check import: `cd /Users/jing1/Developer/github/nanobot && python -c "from nanobot.session.manager import SessionManager; print('OK')"`

## Output

After completing the merge:
1. Commit with message: `merge: upstream/main v0.1.4 with local features preserved`
2. Write a summary of key decisions to `specs/merge-upstream-v0.1.4-decisions.md`
