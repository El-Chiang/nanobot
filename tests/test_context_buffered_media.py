from pathlib import Path

from nanobot.agent.context import ContextBuilder


def _write_fake_png(path: Path) -> None:
    path.write_bytes(b"\x89PNG\r\n\x1a\nfake")


def test_build_user_content_interleaves_buffered_messages_with_media(tmp_path: Path) -> None:
    cat = tmp_path / "cat.png"
    dog = tmp_path / "dog.png"
    _write_fake_png(cat)
    _write_fake_png(dog)

    context = ContextBuilder(tmp_path)
    content = context._build_user_content(
        text="[alice] 看我的猫\n\n[bob] 看我的狗",
        media=[str(cat), str(dog)],
        metadata={
            "collected_messages": [
                {
                    "sender_id": "alice",
                    "content": "看我的猫",
                    "timestamp": "2026-02-18T10:00:00",
                    "media": [str(cat)],
                },
                {
                    "sender_id": "bob",
                    "content": "看我的狗",
                    "timestamp": "2026-02-18T10:00:10",
                    "media": [str(dog)],
                },
            ]
        },
    )

    assert isinstance(content, list)
    assert [block["type"] for block in content] == ["text", "image_url", "text", "image_url"]
    assert content[0]["text"].startswith("[alice] 看我的猫")
    assert "[current_time 2026-02-18 10:00:00]" in content[0]["text"]
    assert "data:image/png;base64," in content[1]["image_url"]["url"]
    assert content[2]["text"].startswith("[bob] 看我的狗")
    assert "[current_time 2026-02-18 10:00:10]" in content[2]["text"]
    assert "data:image/png;base64," in content[3]["image_url"]["url"]


def test_build_user_content_default_media_behavior_unchanged(tmp_path: Path) -> None:
    cat = tmp_path / "cat.png"
    _write_fake_png(cat)

    context = ContextBuilder(tmp_path)
    content = context._build_user_content(
        text="看我的猫",
        media=[str(cat)],
        timestamp="2026-02-18T11:00:00",
    )

    assert isinstance(content, list)
    assert [block["type"] for block in content] == ["image_url", "text"]
    assert "data:image/png;base64," in content[0]["image_url"]["url"]
    assert content[1]["text"].startswith("看我的猫")
    assert "[current_time 2026-02-18 11:00:00]" in content[1]["text"]
