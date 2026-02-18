"""Nanobot status API — tail nanobot logs and expose structured status."""

import asyncio
import os
import re
from collections import deque
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from loguru import logger

NANOBOT_LOG_DIR = Path(os.environ.get("NANOBOT_LOG_DIR", os.path.expanduser("~/.nanobot/logs")))
MAX_LOG_ENTRIES = 200
TAIL_INTERVAL_S = 0.5

_RE_TOOL_CALL = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+) \| INFO\s+\|.*Tool call: "
    r"(?P<tool>\w+)\((?P<args>.*)\)$"
)
_RE_PROCESSING = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+) \| INFO\s+\|.*Processing message from "
    r"(?P<source>\S+): (?P<content>.*)$"
)
_RE_RESPONSE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+) \| INFO\s+\|.*Response to "
    r"(?P<target>\S+): (?P<content>.*)$"
)
_RE_HEARTBEAT = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+) \| INFO\s+\|.*Heartbeat: (?P<msg>.*)$"
)
_RE_TOKEN = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+) \| INFO\s+\|.*Token usage: "
    r"prompt=(?P<prompt>\d+), completion=(?P<completion>\d+), total=(?P<total>\d+)"
)
_RE_CONSOLIDATION = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+) \| INFO\s+\|.*Memory consolidation "
    r"(?P<action>started|done)"
)
_RE_SILENT = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+) \| INFO\s+\|.*Suppress outbound message for "
    r"(?P<target>\S+) due to \[SILENT\] marker"
)

_TOOL_CATEGORIES = {
    "read_file": "read",
    "write_file": "write",
    "edit_file": "write",
    "list_dir": "read",
    "exec": "exec",
    "message": "message",
    "web_search": "search",
    "web_fetch": "search",
    "spawn": "exec",
    "cron": "exec",
}


@dataclass
class LogEntry:
    cursor: int
    ts: str
    event: str
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"cursor": self.cursor, "ts": self.ts, "event": self.event, **self.detail}


@dataclass
class StatusState:
    status: str = "idle"
    current_tool: str | None = None
    current_tool_args: str | None = None
    last_activity_ts: str | None = None
    last_message_from: str | None = None
    tool_calls: int = 0
    messages_in: int = 0
    messages_out: int = 0
    tokens_total: int = 0
    heartbeats: int = 0
    logs: deque = field(default_factory=lambda: deque(maxlen=MAX_LOG_ENTRIES))
    _cursor: int = 0

    def next_cursor(self) -> int:
        self._cursor += 1
        return self._cursor

    def reset_daily(self):
        self.tool_calls = 0
        self.messages_in = 0
        self.messages_out = 0
        self.tokens_total = 0
        self.heartbeats = 0


_state = StatusState()
_tail_task: asyncio.Task | None = None
_current_date: str = ""


def _tool_to_status(tool_name: str) -> str:
    cat = _TOOL_CATEGORIES.get(tool_name, "exec")
    return {"read": "reading", "write": "writing", "exec": "executing",
            "message": "messaging", "search": "searching"}.get(cat, "executing")


def _shorten(text: str, limit: int = 80) -> str:
    return text[:limit] + "..." if len(text) > limit else text


def _parse_line(line: str) -> LogEntry | None:
    """Parse a single log line into a LogEntry, or None if irrelevant."""
    m = _RE_TOOL_CALL.match(line)
    if m:
        tool, args_raw = m.group("tool"), m.group("args")
        _state.status = _tool_to_status(tool)
        _state.current_tool = tool
        _state.current_tool_args = _shorten(args_raw, 120)
        _state.last_activity_ts = m.group("ts")
        _state.tool_calls += 1
        return LogEntry(
            cursor=_state.next_cursor(), ts=m.group("ts"), event="tool_call",
            detail={"tool": tool, "args": _state.current_tool_args,
                    "category": _TOOL_CATEGORIES.get(tool, "exec")},
        )

    m = _RE_PROCESSING.match(line)
    if m:
        _state.status = "thinking"
        _state.current_tool = None
        _state.current_tool_args = None
        _state.last_activity_ts = m.group("ts")
        _state.last_message_from = m.group("source")
        _state.messages_in += 1
        return LogEntry(
            cursor=_state.next_cursor(), ts=m.group("ts"), event="processing",
            detail={"source": m.group("source"), "content": _shorten(m.group("content"))},
        )

    m = _RE_RESPONSE.match(line)
    if m:
        _state.status = "idle"
        _state.current_tool = None
        _state.current_tool_args = None
        _state.last_activity_ts = m.group("ts")
        _state.messages_out += 1
        return LogEntry(
            cursor=_state.next_cursor(), ts=m.group("ts"), event="response",
            detail={"target": m.group("target"), "content": _shorten(m.group("content"))},
        )

    m = _RE_SILENT.match(line)
    if m:
        _state.status = "idle"
        _state.current_tool = None
        _state.current_tool_args = None
        _state.last_activity_ts = m.group("ts")
        return LogEntry(
            cursor=_state.next_cursor(), ts=m.group("ts"), event="silent",
            detail={"target": m.group("target")},
        )

    m = _RE_HEARTBEAT.match(line)
    if m:
        _state.last_activity_ts = m.group("ts")
        _state.heartbeats += 1
        return LogEntry(
            cursor=_state.next_cursor(), ts=m.group("ts"), event="heartbeat",
            detail={"message": m.group("msg")},
        )

    m = _RE_TOKEN.match(line)
    if m:
        _state.tokens_total += int(m.group("total"))
        return None  # token stats update only, don't pollute logs

    m = _RE_CONSOLIDATION.match(line)
    if m:
        action = m.group("action")
        if action == "started":
            _state.status = "consolidating"
        elif action == "done":
            _state.status = "idle"
        return LogEntry(
            cursor=_state.next_cursor(), ts=m.group("ts"), event="consolidation",
            detail={"action": action},
        )

    return None


def _get_log_path() -> Path:
    """Return today's nanobot log file path."""
    return NANOBOT_LOG_DIR / f"nanobot_{date.today().isoformat()}.log"


async def _tail_loop():
    """Background task: tail nanobot log file, parse lines, update state."""
    global _current_date
    file_pos = 0
    current_path: Path | None = None

    while True:
        try:
            today = date.today().isoformat()
            log_path = _get_log_path()

            # Date rollover: reset stats and file position
            if today != _current_date:
                _current_date = today
                _state.reset_daily()
                file_pos = 0
                current_path = None
                logger.info("Status tail: new day {}", today)

            if not log_path.exists():
                await asyncio.sleep(TAIL_INTERVAL_S * 4)
                continue

            # File changed (rotation, new day)
            if current_path != log_path:
                current_path = log_path
                # Start from end of existing file on first connect
                if file_pos == 0:
                    file_pos = log_path.stat().st_size
                    logger.info("Status tail: attached to {} at pos {}", log_path.name, file_pos)

            # Check if file was truncated/rotated
            current_size = log_path.stat().st_size
            if current_size < file_pos:
                file_pos = 0

            if current_size > file_pos:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(file_pos)
                    new_data = f.read()
                    file_pos = f.tell()

                for line in new_data.splitlines():
                    entry = _parse_line(line)
                    if entry:
                        _state.logs.append(entry)

        except Exception as e:
            logger.error("Status tail error: {}", e)

        await asyncio.sleep(TAIL_INTERVAL_S)


async def start_tail():
    """Start the background log tail task."""
    global _tail_task
    if _tail_task is None or _tail_task.done():
        _tail_task = asyncio.create_task(_tail_loop())
        logger.info("Status tail task started")


async def stop_tail():
    """Stop the background log tail task."""
    global _tail_task
    if _tail_task and not _tail_task.done():
        _tail_task.cancel()
        try:
            await _tail_task
        except asyncio.CancelledError:
            pass
        _tail_task = None
        logger.info("Status tail task stopped")


# ---------------------------------------------------------------------------
# Helpers for response mapping (ported from m5stack-nanobot/server/main.py)
# ---------------------------------------------------------------------------

def _map_status_to_mood(status: str) -> str:
    if status == "thinking":
        return "excited"
    if status in ("reading", "writing", "executing", "searching", "consolidating"):
        return "working"
    return "idle"


def _to_hhmm(ts: str | None) -> str:
    if not ts:
        return "--:--"
    if len(ts) >= 16:
        return ts[11:16]
    return ts


def _build_action(raw_status: dict) -> str:
    status = raw_status.get("status", "idle")
    tool = raw_status.get("current_tool")
    if tool:
        return f"{status}: {tool}"
    return status


def _map_logs(raw_logs: list[dict]) -> list[dict]:
    mapped = []
    for item in raw_logs:
        event = item.get("event", "event")
        detail = (
            item.get("tool")
            or item.get("content")
            or item.get("message")
            or item.get("target")
            or ""
        )
        mapped.append({
            "cursor": item.get("cursor", 0),
            "time": _to_hhmm(item.get("ts")),
            "action": event,
            "detail": detail,
        })
    return mapped


def get_status(cursor: int = 0) -> dict:
    """Return current status + incremental logs since cursor."""
    incremental = [e.to_dict() for e in _state.logs if e.cursor > cursor]

    return {
        "status": _state.status,
        "current_tool": _state.current_tool,
        "current_tool_args": _state.current_tool_args,
        "last_activity_ts": _state.last_activity_ts,
        "last_message_from": _state.last_message_from,
        "stats": {
            "tool_calls": _state.tool_calls,
            "messages_in": _state.messages_in,
            "messages_out": _state.messages_out,
            "tokens_total": _state.tokens_total,
            "heartbeats": _state.heartbeats,
        },
        "logs": incremental,
        "cursor": _state._cursor,
    }


def get_aggregated_status(cursor: int = 0) -> dict:
    """Return aggregated status matching m5stack-nanobot /api/status format."""
    raw = get_status(cursor)
    stats = raw.get("stats", {})
    return {
        "mood": _map_status_to_mood(raw.get("status", "idle")),
        "action": _build_action(raw),
        "logs": _map_logs(raw.get("logs", [])),
        "stats": {
            "messages": stats.get("messages_in", 0) + stats.get("messages_out", 0),
            "tools": stats.get("tool_calls", 0),
            "memories": 0,
            "uptime_min": 0,
            "tokens_total": stats.get("tokens_total", 0),
        },
        "cursor": raw.get("cursor", cursor),
    }
