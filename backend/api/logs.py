import asyncio
import json

from fastapi import APIRouter
from starlette.responses import StreamingResponse

from backend.log_stream import log_stream_handler

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("/stream")
async def log_stream(level: str | None = None):
    """SSE endpoint for real-time server logs."""
    q = log_stream_handler.subscribe()
    level_filter = level.upper() if level else None

    async def event_generator():
        try:
            while True:
                try:
                    entry = await asyncio.wait_for(q.get(), timeout=30)
                    if level_filter and entry["level"] != level_filter:
                        continue
                    yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield f": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            log_stream_handler.unsubscribe(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/recent")
async def recent_logs(
    count: int = 100,
    level: str | None = None,
    source: str = "memory",
    offset: int = 0,
):
    """Get recent log entries. source=memory (default) or source=file for history."""
    if source == "file":
        entries = log_stream_handler.read_history(count=count, offset=offset, level=level)
    else:
        entries = log_stream_handler.get_recent(count)
        if level:
            level_upper = level.upper()
            entries = [e for e in entries if e["level"] == level_upper]
    return {"items": entries, "total": len(entries)}
