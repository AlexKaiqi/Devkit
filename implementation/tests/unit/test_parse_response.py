"""L1 Unit: parse_response — text/attachment splitting from bot.py."""

import re

CODE_BLOCK_RE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)


def parse_response(text: str) -> dict:
    """Mirror of implementation/channels/telegram/bot.py:parse_response."""
    attachments = []
    for m in CODE_BLOCK_RE.finditer(text):
        attachments.append({
            "type": "code",
            "language": m.group(1) or "",
            "content": m.group(2).strip(),
        })
    spoken = CODE_BLOCK_RE.sub("", text).strip()
    spoken = re.sub(r"\n{3,}", "\n\n", spoken)
    return {"spoken": spoken, "attachments": attachments}


# ── Tests ────────────────────────────────────────────

class TestPlainText:

    def test_simple_text(self):
        result = parse_response("Hello, master!")
        assert result["spoken"] == "Hello, master!"
        assert result["attachments"] == []

    def test_multiline_text(self):
        result = parse_response("Line 1\nLine 2\nLine 3")
        assert "Line 1" in result["spoken"]
        assert result["attachments"] == []

    def test_empty_string(self):
        result = parse_response("")
        assert result["spoken"] == ""
        assert result["attachments"] == []


class TestCodeBlocks:

    def test_single_code_block(self):
        text = "Here's code:\n```python\nprint('hi')\n```"
        result = parse_response(text)
        assert len(result["attachments"]) == 1
        assert result["attachments"][0]["language"] == "python"
        assert result["attachments"][0]["content"] == "print('hi')"
        assert "print" not in result["spoken"]

    def test_code_block_without_language(self):
        text = "Output:\n```\nfoo bar\n```"
        result = parse_response(text)
        assert result["attachments"][0]["language"] == ""
        assert result["attachments"][0]["content"] == "foo bar"

    def test_multiple_code_blocks(self):
        text = "A:\n```js\nlet x=1\n```\nB:\n```bash\necho hi\n```"
        result = parse_response(text)
        assert len(result["attachments"]) == 2
        assert result["attachments"][0]["language"] == "js"
        assert result["attachments"][1]["language"] == "bash"

    def test_spoken_text_strips_code_blocks(self):
        text = "First\n```py\ncode\n```\nSecond"
        result = parse_response(text)
        assert "code" not in result["spoken"]
        assert "First" in result["spoken"]
        assert "Second" in result["spoken"]


class TestMixedContent:

    def test_text_with_code_and_emoji(self):
        text = "主人好 🎀\n```json\n{\"key\": \"val\"}\n```\n希露菲完成了"
        result = parse_response(text)
        assert "主人好" in result["spoken"]
        assert "希露菲完成了" in result["spoken"]
        assert len(result["attachments"]) == 1
        assert result["attachments"][0]["language"] == "json"

    def test_excessive_newlines_collapsed(self):
        text = "Line1\n\n\n\n\nLine2"
        result = parse_response(text)
        assert "\n\n\n" not in result["spoken"]
        assert "Line1" in result["spoken"]
        assert "Line2" in result["spoken"]

    def test_code_block_multiline_content(self):
        text = "Result:\n```sql\nSELECT *\nFROM users\nWHERE id = 1\n```"
        result = parse_response(text)
        assert "SELECT" in result["attachments"][0]["content"]
        assert "WHERE" in result["attachments"][0]["content"]
