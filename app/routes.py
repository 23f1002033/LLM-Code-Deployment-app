"""
FastAPI endpoint definitions and application factory.
"""

import os
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import JSONResponse, PlainTextResponse, HTMLResponse

from app import __version__
from app.config import settings, flush_log_handlers
from app.models import TaskRequest, HealthResponse
from app import pipeline
from app.dashboard_page import DASHBOARD_HTML

log = logging.getLogger("deployment_service")


# ---- in-memory rate limiter (no extra dep needed) ----

class _RateLimiter:
    """Sliding-window rate limiter keyed by client IP."""

    def __init__(self, max_requests: int = 15, window: int = 60):
        self._max = max_requests
        self._window = window
        self._hits: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> bool:
        now = time.time()
        self._hits[key] = [
            t for t in self._hits[key] if now - t < self._window
        ]
        if len(self._hits[key]) >= self._max:
            return False
        self._hits[key].append(now)
        return True


_limiter = _RateLimiter()


# ---- background task bookkeeping ----

_bg_tasks: list[asyncio.Task] = []


def _on_bg_task_done(task: asyncio.Task):
    """Callback for completed background tasks — logs errors and cleans up."""
    try:
        exc = task.exception()
        if exc:
            log.error("Background task error: %s", exc)
    except asyncio.CancelledError:
        log.warning("Background task cancelled")
    finally:
        flush_log_handlers()
        _bg_tasks[:] = [t for t in _bg_tasks if not t.done()]


# ---- application lifespan ----

@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Startup and shutdown lifecycle management."""
    # startup: heartbeat loop
    async def heartbeat():
        while True:
            log.info(
                "[heartbeat] active_tasks=%d", pipeline.get_active_count()
            )
            flush_log_handlers()
            await asyncio.sleep(settings.KEEP_ALIVE_INTERVAL)

    hb = asyncio.create_task(heartbeat())
    log.info("Service started (v%s)", __version__)

    yield

    # shutdown: cancel heartbeat + drain pending work
    hb.cancel()
    log.info("Shutting down, cancelling %d task(s)...", len(_bg_tasks))
    for t in _bg_tasks:
        if not t.done():
            t.cancel()
    await asyncio.sleep(0.5)
    flush_log_handlers()


# ---- app factory ----

def create_app() -> FastAPI:
    """Construct and return the configured FastAPI application."""

    app = FastAPI(
        title="LLM Code Deployment Service",
        description=(
            "Automated pipeline that generates web applications using "
            "large language models and deploys them to GitHub Pages."
        ),
        version=__version__,
        lifespan=_lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ---- task submission ----

    @app.post("/ready", status_code=200, tags=["Tasks"])
    async def receive_task(task_data: TaskRequest, request: Request):
        """
        Accept a code generation task from the evaluation server.
        The task is validated, queued, and processed in the background.
        """
        if task_data.secret != settings.STUDENT_SECRET:
            client_ip = request.client.host if request.client else "unknown"
            log.warning("Unauthorized /ready attempt from %s", client_ip)
            raise HTTPException(status_code=401, detail="Unauthorized")

        client_key = request.client.host if request.client else "global"
        if not _limiter.check(client_key):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

        pipeline.record_task(task_data)
        bg = asyncio.create_task(pipeline.run_pipeline(task_data))
        bg.add_done_callback(_on_bg_task_done)
        _bg_tasks.append(bg)

        log.info("Task queued: %s (round %d)", task_data.task, task_data.round)
        flush_log_handlers()

        return JSONResponse(
            status_code=200,
            content={
                "status": "accepted",
                "task": task_data.task,
                "message": "Task received, processing started.",
            },
        )

    # ---- monitoring ----

    @app.get("/", tags=["Monitoring"])
    async def root():
        """Service discovery endpoint."""
        return {
            "service": "LLM Code Deployment Service",
            "version": __version__,
            "dashboard": "/dashboard",
            "docs": "/docs",
            "health": "/health",
        }

    @app.get("/health", response_model=HealthResponse, tags=["Monitoring"])
    async def health():
        """Health check endpoint."""
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            version=__version__,
            active_tasks=pipeline.get_active_count(),
        )

    @app.get("/status", tags=["Monitoring"])
    async def get_status():
        """Task history and queue status."""
        records = pipeline.get_task_records()
        return {
            "active_tasks": pipeline.get_active_count(),
            "total_tasks": len(records),
            "recent": [r.model_dump() for r in records[:20]],
        }

    @app.get("/logs", tags=["Monitoring"])
    async def get_logs(lines: int = Query(200, ge=1, le=5000)):
        """Retrieve the last N lines from the application log."""
        path = settings.LOG_FILE_PATH
        if not os.path.exists(path):
            return PlainTextResponse("No log file found.", status_code=404)

        try:
            with open(path, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                buffer = bytearray()

                while size > 0 and len(buffer) < lines * 250:
                    chunk = min(4096, size)
                    f.seek(size - chunk)
                    buffer.extend(f.read(chunk))
                    size -= chunk

                all_lines = buffer.decode(errors="replace").splitlines()
                return PlainTextResponse("\n".join(all_lines[-lines:]))
        except Exception as exc:
            log.error("Error reading logs: %s", exc)
            return PlainTextResponse(f"Error: {exc}", status_code=500)

    # ---- embedded dashboard ----

    @app.get("/dashboard", tags=["Monitoring"], include_in_schema=False)
    async def dashboard():
        """Visual monitoring dashboard (built-in, no separate process)."""
        return HTMLResponse(content=DASHBOARD_HTML)

    return app
