import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.db.database import db
from backend.scraper.engine import engine
from backend.queue.scheduler import scheduler
from backend.api.router import api_router
from backend.log_stream import log_stream_handler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# Attach log stream handler to root logger
logging.getLogger().addHandler(log_stream_handler)
logger = logging.getLogger(__name__)

# Global shutdown event
shutdown_event = asyncio.Event()


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_event.set()


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings.ensure_dirs()
    await db.connect()
    logger.info("Database connected")

    await engine.start()
    logger.info("Scraper engine started")

    await scheduler.start()
    logger.info("Task scheduler started")

    # Start MCP SSE server in background (only in main process, not reload workers)
    import os
    mcp_task = None
    if not os.environ.get("UVICORN_WORKER"):
        mcp_task = asyncio.create_task(_start_mcp_server())

    yield

    # Shutdown - graceful cleanup
    logger.info("Starting graceful shutdown...")

    if mcp_task:
        mcp_task.cancel()
        try:
            await mcp_task
        except asyncio.CancelledError:
            pass

    # Stop scheduler first (no new tasks)
    await scheduler.stop()
    logger.info("Scheduler stopped")

    # Stop browser engine
    await engine.stop()
    logger.info("Engine stopped")

    # Close database with WAL checkpoint
    await db.close()
    logger.info("Database closed")

    logger.info("Shutdown complete")


app = FastAPI(
    title="Douyin Scraper API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

# Serve downloaded media files
settings.MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(settings.MEDIA_DIR)), name="media")

# Serve frontend static files in production (when frontend/dist exists)
_frontend_dist = settings.BASE_DIR / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="frontend-assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Fallback: serve index.html for SPA routing."""
        file_path = _frontend_dist / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_frontend_dist / "index.html"))


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


async def _start_mcp_server():
    """Run MCP SSE server as a background task."""
    try:
        from backend.mcp.server import mcp_server
        logger.info("MCP SSE server starting on port %s", settings.MCP_PORT)
        await mcp_server.run_sse_async()
    except asyncio.CancelledError:
        logger.info("MCP server stopped")
    except Exception:
        logger.exception("MCP server error")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=False,
    )
