import asyncio
import json
import logging
import time
from collections import deque


class LogStreamHandler(logging.Handler):
    """Custom log handler that pushes log records to SSE subscribers."""

    def __init__(self, max_buffer: int = 500):
        super().__init__()
        self._subscribers: list[asyncio.Queue] = []
        self._buffer: deque = deque(maxlen=max_buffer)
        self._loop: asyncio.AbstractEventLoop | None = None

    def emit(self, record: logging.LogRecord):
        entry = {
            "timestamp": time.strftime("%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "name": record.name,
            "message": self.format(record),
        }
        self._buffer.append(entry)

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


log_stream_handler = LogStreamHandler()
log_stream_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
