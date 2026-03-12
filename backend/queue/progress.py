import asyncio
import json
import time
from collections import defaultdict


class ProgressManager:
    """Manages task progress events and SSE subscriptions."""

    def __init__(self):
        self._subscribers: dict[int, list[asyncio.Queue]] = defaultdict(list)
        self._all_subscribers: list[asyncio.Queue] = []  # subscribe to all tasks
        self._latest: dict[int, dict] = {}

    def update(self, task_id: int, progress: float, step: str, detail: str = ""):
        """Push a progress update for a task."""
        event = {
            "task_id": task_id,
            "progress": round(progress, 2),
            "step": step,
            "detail": detail,
            "timestamp": time.time(),
        }
        self._latest[task_id] = event

        # Notify task-specific subscribers
        for q in self._subscribers.get(task_id, []):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

        # Notify global subscribers
        for q in self._all_subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def subscribe(self, task_id: int | None = None) -> asyncio.Queue:
        """Subscribe to progress events. If task_id is None, subscribe to all."""
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        if task_id is not None:
            self._subscribers[task_id].append(q)
        else:
            self._all_subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue, task_id: int | None = None):
        """Remove a subscriber."""
        if task_id is not None:
            subs = self._subscribers.get(task_id, [])
            if q in subs:
                subs.remove(q)
        else:
            if q in self._all_subscribers:
                self._all_subscribers.remove(q)

    def get_latest(self, task_id: int) -> dict | None:
        return self._latest.get(task_id)

    def clear(self, task_id: int):
        if task_id in self._latest:
            del self._latest[task_id]
        if task_id in self._subscribers:
            del self._subscribers[task_id]


progress_manager = ProgressManager()
