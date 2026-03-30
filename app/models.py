"""
Pydantic models for request validation and internal state tracking.
"""

from typing import List, Optional
from datetime import datetime, timezone

from pydantic import BaseModel


class Attachment(BaseModel):
    """File attachment — accepts data URIs or remote URLs."""
    name: str
    url: str


class TaskRequest(BaseModel):
    """Incoming task payload from the evaluation server."""
    task: str
    email: str
    round: int
    brief: str
    evaluation_url: str
    nonce: str
    secret: str
    attachments: List[Attachment] = []


class TaskRecord(BaseModel):
    """Internal tracking record for a submitted task."""
    task_id: str
    email: str
    round: int
    brief_preview: str
    received_at: str
    status: str = "queued"
    pages_url: Optional[str] = None
    repo_url: Optional[str] = None
    error_message: Optional[str] = None

    @classmethod
    def from_request(cls, req: TaskRequest) -> "TaskRecord":
        preview = req.brief[:200] + "..." if len(req.brief) > 200 else req.brief
        return cls(
            task_id=req.task,
            email=req.email,
            round=req.round,
            brief_preview=preview,
            received_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )


class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str = "healthy"
    timestamp: str
    version: str
    active_tasks: int = 0
