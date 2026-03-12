"""search tool — web search via SearXNG."""

import os

import aiohttp

from tools import tool

SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://localhost:8080")


@tool(
    name="search",
    description="Search the web via SearXNG. Returns title + URL + snippet for each result.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {"type": "integer", "description": "Max results (default 5)"},
        },
        "required": ["query"],
    },
)
async def handle(args: dict, ctx) -> str:
    query = args["query"]
    max_results = args.get("max_results", 5)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{SEARXNG_URL}/search",
                params={"q": query, "format": "json"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
        results = data.get("results", [])[:max_results]
        if not results:
            return "No results found."
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title', '')}")
            lines.append(f"   {r.get('url', '')}")
            snippet = r.get("content", "")
            if snippet:
                lines.append(f"   {snippet[:200]}")
            lines.append("")
        return "\n".join(lines)
    except Exception as e:
        return f"[error] Search failed: {e}"
