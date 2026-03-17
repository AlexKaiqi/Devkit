"""WatchlistChecker — background task that monitors subscriptions for changes."""

import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Awaitable

log = logging.getLogger("watchlist-checker")


class WatchlistChecker:
    """Periodically checks watchlist entries and notifies on changes."""

    def __init__(
        self,
        data_path: Path,
        run_tool_fn: Callable[..., Awaitable[str]],
        interval_sec: int = 300,
    ):
        self._data_path = data_path
        self._run_tool = run_tool_fn
        self._interval_sec = interval_sec

    async def start(self) -> None:
        asyncio.create_task(self._loop())

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval_sec)
            try:
                await self._check_all()
            except Exception:
                log.exception("WatchlistChecker._check_all error")

    async def _check_all(self) -> None:
        if not self._data_path.exists():
            return

        try:
            entries = json.loads(self._data_path.read_text(encoding="utf-8"))
        except Exception:
            log.warning("Failed to read watchlist data")
            return

        now = datetime.now(timezone.utc)
        changed = False

        for entry in entries:
            last_checked_str = entry.get("last_checked_at", "1970-01-01T00:00:00+00:00")
            try:
                last_checked = datetime.fromisoformat(last_checked_str)
                if last_checked.tzinfo is None:
                    last_checked = last_checked.replace(tzinfo=timezone.utc)
            except Exception:
                last_checked = datetime.fromtimestamp(0, tz=timezone.utc)

            interval_hours = float(entry.get("interval_hours", 24))
            elapsed_hours = (now - last_checked).total_seconds() / 3600

            if elapsed_hours < interval_hours:
                continue  # not due yet

            query = entry.get("query", "")
            topic = entry.get("topic", "")
            session_key = entry.get("session_key", "")
            old_hash = entry.get("last_result_hash", "")

            try:
                result = await self._run_tool("search", {"query": query}, session_key=session_key)
            except Exception as e:
                log.warning("watchlist search failed for %s: %s", topic, e)
                continue

            new_hash = hashlib.md5(result.encode()).hexdigest()

            if new_hash != old_hash:
                snippet = result[:200]
                msg = f"[监控] {topic} 有更新：{snippet}"
                try:
                    await self._run_tool("notify", {"message": msg}, session_key=session_key)
                except Exception as e:
                    log.warning("watchlist notify failed for %s: %s", topic, e)

            entry["last_checked_at"] = now.isoformat()
            entry["last_result_hash"] = new_hash
            changed = True

        if changed:
            try:
                self._data_path.write_text(
                    json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            except Exception:
                log.warning("Failed to save watchlist after check")
