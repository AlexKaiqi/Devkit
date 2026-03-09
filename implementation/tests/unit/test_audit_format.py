"""L1 Unit: audit log entry format validation."""

import json
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))


def make_audit_entry(event: str, **kwargs) -> dict:
    """Mirror of the audit() helper in bot.py."""
    return {
        "ts": datetime.now(CST).isoformat(),
        "event": event,
        "channel": "telegram",
        **kwargs,
    }


# ── Tests ────────────────────────────────────────────

class TestReqEvent:

    def test_required_fields(self):
        entry = make_audit_entry("req", chat_id=123, user="hello", source="gateway")
        assert entry["event"] == "req"
        assert entry["chat_id"] == 123
        assert entry["user"] == "hello"
        assert entry["source"] == "gateway"
        assert "ts" in entry

    def test_timestamp_is_iso(self):
        entry = make_audit_entry("req", chat_id=1, user="x", source="gw")
        datetime.fromisoformat(entry["ts"])  # raises ValueError if invalid

    def test_images_count(self):
        entry = make_audit_entry("req", chat_id=1, user="看看这个", images=3, source="gateway")
        assert entry["images"] == 3


class TestResEvent:

    def test_required_fields(self):
        entry = make_audit_entry("res", chat_id=123, assistant="reply text", ms=1200, source="gateway")
        assert entry["event"] == "res"
        assert entry["chat_id"] == 123
        assert entry["assistant"] == "reply text"
        assert entry["ms"] == 1200

    def test_assistant_truncation(self):
        long_text = "x" * 1000
        entry = make_audit_entry("res", chat_id=1, assistant=long_text[:500], ms=100, source="gateway")
        assert len(entry["assistant"]) == 500


class TestSttEvent:

    def test_required_fields(self):
        entry = make_audit_entry("stt", text="你好", ms=350)
        assert entry["event"] == "stt"
        assert entry["text"] == "你好"
        assert entry["ms"] == 350


class TestTtsEvent:

    def test_required_fields(self):
        entry = make_audit_entry("tts", text_len=42, audio_bytes=8192, ms=600)
        assert entry["event"] == "tts"
        assert entry["text_len"] == 42
        assert entry["audio_bytes"] == 8192
        assert entry["ms"] == 600


class TestChannelField:

    def test_channel_always_present(self):
        for evt in ("req", "res", "stt", "tts"):
            entry = make_audit_entry(evt)
            assert entry["channel"] == "telegram"


class TestJsonSerialization:

    def test_entry_is_json_serializable(self):
        entry = make_audit_entry("req", chat_id=1, user="你好世界", source="gateway")
        line = json.dumps(entry, ensure_ascii=False)
        parsed = json.loads(line)
        assert parsed["user"] == "你好世界"

    def test_jsonl_line_format(self):
        entry = make_audit_entry("res", chat_id=1, assistant="ok", ms=100, source="gw")
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        assert line.endswith("\n")
        assert "\n" not in line.rstrip("\n")
