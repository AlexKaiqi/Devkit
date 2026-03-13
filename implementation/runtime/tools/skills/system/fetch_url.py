"""fetch_url tool — fetch a URL and return readable text content."""

import re

import aiohttp

from tools import tool


@tool(
    name="fetch_url",
    description="Fetch a URL and return its text content (HTML stripped to plain text). Use for reading articles, documentation, API responses, etc.",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL to fetch"},
            "max_chars": {"type": "integer", "description": "Max characters to return (default 8000)"},
        },
        "required": ["url"],
    },
)
async def handle(args: dict, ctx) -> str:
    url = args["url"]
    max_chars = args.get("max_chars", 8000)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Devkit-Agent/1.0)",
        "Accept": "text/html,application/xhtml+xml,application/json,text/plain,*/*",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=20),
                allow_redirects=True,
            ) as resp:
                content_type = resp.headers.get("Content-Type", "")
                raw = await resp.text(errors="replace")

        # Strip HTML tags if HTML response
        if "html" in content_type or raw.strip().startswith("<"):
            # Remove script/style blocks
            raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
            # Remove all tags
            raw = re.sub(r"<[^>]+>", " ", raw)
            # Decode common HTML entities
            raw = raw.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')

        # Collapse whitespace
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        raw = re.sub(r" {2,}", " ", raw)
        raw = raw.strip()

        if len(raw) > max_chars:
            raw = raw[:max_chars] + f"\n...(truncated, total {len(raw)} chars)"
        return raw or "(empty response)"
    except Exception as e:
        return f"[error] fetch_url {url}: {e}"
