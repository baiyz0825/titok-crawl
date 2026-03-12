import asyncio
import json
import logging
import os
import time
from collections import deque
from pathlib import Path


class LogStreamHandler(logging.Handler):
    """Custom log handler that pushes log records to SSE subscribers and persists to file."""

    def __init__(self, max_buffer: int = 500, log_file: Path | None = None):
        super().__init__()
        self._subscribers: list[asyncio.Queue] = []
        self._buffer: deque = deque(maxlen=max_buffer)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._log_file = log_file
        self._file_handle = None
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            self._file_handle = open(log_file, "a", encoding="utf-8")

    def emit(self, record: logging.LogRecord):
        entry = {
            "timestamp": time.strftime("%H:%M:%S", time.localtime(record.created)),
            "full_timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "name": record.name,
            "message": self.format(record),
        }
        self._buffer.append(entry)

        # Persist to file
        if self._file_handle:
            try:
                self._file_handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
                self._file_handle.flush()
            except Exception:
                pass

        for q in list(self._subscribers):
            try:
                q.put_nowait(entry)
            except asyncio.QueueFull:
                pass

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._subscribers:
            self._subscribers.remove(q)

    def get_recent(self, count: int = 50) -> list[dict]:
        return list(self._buffer)[-count:]

    def read_history(self, count: int = 500, offset: int = 0, level: str | None = None) -> list[dict]:
        """Read historical logs from the persisted file (newest first)."""
        if not self._log_file or not self._log_file.exists():
            return []

        entries = []
        try:
            with open(self._log_file, "r", encoding="utf-8") as f:
                all_lines = f.readlines()

            # Read from end (newest first)
            for line in reversed(all_lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if level and entry.get("level") != level.upper():
                        continue
                    if offset > 0:
                        offset -= 1
                        continue
                    entries.append(entry)
                    if len(entries) >= count:
                        break
                except json.JSONDecodeError:
                    continue
        except Exception:
            pass

        # Return in chronological order (oldest first)
        entries.reverse()
        return entries

    def close(self):
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None
        super().close()


def _create_handler():
    from backend.config import settings
    handler = LogStreamHandler(log_file=settings.LOG_FILE)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    return handler


log_stream_handler = _create_handler()
