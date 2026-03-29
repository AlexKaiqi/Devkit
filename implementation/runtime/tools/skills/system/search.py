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
            "engines": {
                "type": "string",
                "description": "Comma-separated engine list (e.g. 'google,bing'). Default: all enabled engines.",
            },
        },
        "required": ["query"],
    },
)
async def handle(args: dict, ctx) -> str:
    query = args["query"]
    max_results = args.get("max_results", 5)
    engines = args.get("engines", "")

    params = {"q": query, "format": "json"}
    if engines:
        params["engines"] = engines

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{SEARXNG_URL}/search",
                params=params,
                timeout=aiohttp.ClientTimeout(total=12),
            ) as resp:
                if resp.status != 200:
                    return f"[error] SearXNG returned HTTP {resp.status}. 服务可能未启动，运行 ./start.sh 启动。"
                data = await resp.json()

        results = data.get("results", [])[:max_results]
        if not results:
            return f"No results found for '{query}'."

        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "").strip()
            url = r.get("url", "")
            snippet = r.get("content", "").strip()
            engine = r.get("engine", "")
            lines.append(f"{i}. {title}")
            lines.append(f"   {url}")
            if snippet:
                lines.append(f"   {snippet[:300]}")
            if engine:
                lines.append(f"   [via {engine}]")
            lines.append("")
        return "\n".join(lines)

    except aiohttp.ClientConnectorError:
        return (
            f"[error] 无法连接 SearXNG ({SEARXNG_URL})。"
            "请确认 Docker 已启动并运行 ./start.sh。"
            "也可以使用 fetch_url 工具直接访问已知 URL。"
        )
    except TimeoutError:
        return (
            f"[error] SearXNG 搜索超时（12s）。"
            "可能是容器内出站网络不稳定。"
            "可以尝试指定引擎: engines='google' 或 engines='bing'"
        )
    except Exception as e:
        return f"[error] Search failed: {e}"
