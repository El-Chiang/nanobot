from nanobot.session.manager import Session


def _assistant_tool_call(call_id: str) -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": "_tool_use_summary", "arguments": "{}"},
    }


def test_get_history_trims_to_user_boundary_after_max_window_cut() -> None:
    s = Session(key="dingtalk:test")
    s.add_message("user", "u1")
    s.add_message("assistant", "a1", tool_calls=[_assistant_tool_call("c1")])
    s.add_message("tool", "t1", tool_call_id="c1", name="_tool_use_summary")
    s.add_message("user", "u2")

    history = s.get_history(max_messages=2)

    assert len(history) == 1
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "u2"


def test_get_history_has_no_orphan_tool_messages_in_trimmed_window() -> None:
    s = Session(key="dingtalk:test")
    # Build multiple turns so max window can cut into the middle of a tool pair.
    for i in range(6):
        call_id = f"c{i}"
        s.add_message("user", f"u{i}")
        s.add_message("assistant", f"a{i}", tool_calls=[_assistant_tool_call(call_id)])
        s.add_message("tool", f"t{i}", tool_call_id=call_id, name="_tool_use_summary")

    history = s.get_history(max_messages=5)

    assert history
    assert history[0]["role"] == "user"

    seen_tool_call_ids: set[str] = set()
    for msg in history:
        if msg["role"] == "assistant" and "tool_calls" in msg:
            for tc in msg["tool_calls"]:
                seen_tool_call_ids.add(tc["id"])
        if msg["role"] == "tool":
            assert msg["tool_call_id"] in seen_tool_call_ids
