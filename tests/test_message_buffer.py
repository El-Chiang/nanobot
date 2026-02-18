import asyncio
from pathlib import Path
from typing import Any

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider, LLMResponse


class DummyProvider(LLMProvider):
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> LLMResponse:
        raise AssertionError("DummyProvider.chat should not be called in these tests")

    def get_default_model(self) -> str:
        return "dummy/test-model"


@pytest.mark.asyncio
async def test_message_bus_merges_buffered_messages_in_order() -> None:
    bus = MessageBus()
    current = InboundMessage(channel="telegram", sender_id="u0", chat_id="c1", content="current")
    await bus.publish_inbound(current)
    consumed = await bus.consume_inbound()

    await bus.publish_inbound(InboundMessage(channel="telegram", sender_id="alice", chat_id="c1", content="one"))
    await bus.publish_inbound(InboundMessage(channel="telegram", sender_id="bob", chat_id="c1", content="two"))

    assert bus.inbound_size == 0
    await bus.complete_inbound_turn(consumed)

    merged = await asyncio.wait_for(bus.consume_inbound(), timeout=1.0)
    assert merged.content == "[alice] one\n\n[bob] two"
    assert merged.metadata["collected_count"] == 2
    assert [item["sender_id"] for item in merged.metadata["collected_messages"]] == ["alice", "bob"]
    assert [item["content"] for item in merged.metadata["collected_messages"]] == ["one", "two"]


@pytest.mark.asyncio
async def test_message_bus_only_buffers_same_session() -> None:
    bus = MessageBus()
    current = InboundMessage(channel="telegram", sender_id="u0", chat_id="c1", content="current")
    await bus.publish_inbound(current)
    consumed = await bus.consume_inbound()

    other_session = InboundMessage(channel="telegram", sender_id="u2", chat_id="c2", content="other")
    same_session = InboundMessage(channel="telegram", sender_id="u1", chat_id="c1", content="follow")
    await bus.publish_inbound(other_session)
    await bus.publish_inbound(same_session)

    await bus.complete_inbound_turn(consumed)

    next_msg = await asyncio.wait_for(bus.consume_inbound(), timeout=1.0)
    assert next_msg.chat_id == "c2"
    await bus.complete_inbound_turn(next_msg)

    merged = await asyncio.wait_for(bus.consume_inbound(), timeout=1.0)
    assert merged.chat_id == "c1"
    assert merged.content == "follow"


@pytest.mark.asyncio
async def test_agent_loop_processes_buffered_messages_as_single_followup_turn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bus = MessageBus()
    agent = AgentLoop(bus=bus, provider=DummyProvider(), workspace=tmp_path)

    processed: list[InboundMessage] = []
    first_started = asyncio.Event()
    release_first = asyncio.Event()

    async def fake_process_message(msg: InboundMessage, session_key: str | None = None) -> OutboundMessage | None:
        processed.append(msg)
        if len(processed) == 1:
            first_started.set()
            await release_first.wait()
        else:
            agent.stop()
        return None

    monkeypatch.setattr(agent, "_process_message", fake_process_message)

    task = asyncio.create_task(agent.run())
    try:
        await bus.publish_inbound(
            InboundMessage(channel="telegram", sender_id="u0", chat_id="c1", content="current")
        )
        await asyncio.wait_for(first_started.wait(), timeout=1.0)

        await bus.publish_inbound(
            InboundMessage(channel="telegram", sender_id="alice", chat_id="c1", content="one")
        )
        await bus.publish_inbound(
            InboundMessage(channel="telegram", sender_id="bob", chat_id="c1", content="two")
        )
        release_first.set()

        await asyncio.wait_for(task, timeout=2.0)
    finally:
        if not task.done():
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    assert len(processed) == 2
    followup = processed[1]
    assert followup.content == "[alice] one\n\n[bob] two"
    assert [item["sender_id"] for item in followup.metadata["collected_messages"]] == ["alice", "bob"]
