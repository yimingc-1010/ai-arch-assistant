"""In-memory task registry for background jobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid


@dataclass
class Task:
    id: str
    type: str           # "ingest_pdf" | "crawl" | "ingest_crawled"
    status: str         # "pending" | "running" | "done" | "error"
    progress: int       # 0–100
    message: str
    result: Optional[dict] = None
    error: Optional[str] = None
    crawl_data: Optional[dict] = None  # crawl tasks only: raw crawler result
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


_tasks: dict[str, Task] = {}


def create_task(type: str) -> Task:
    task = Task(
        id=str(uuid.uuid4()),
        type=type,
        status="pending",
        progress=0,
        message="排隊中...",
    )
    _tasks[task.id] = task
    return task


def get_task(task_id: str) -> Optional[Task]:
    return _tasks.get(task_id)


def list_tasks() -> list[Task]:
    """Return tasks sorted by created_at descending, max 50."""
    sorted_tasks = sorted(_tasks.values(), key=lambda t: t.created_at, reverse=True)
    return sorted_tasks[:50]


def task_to_dict(task: Task) -> dict:
    return {
        "id": task.id,
        "type": task.type,
        "status": task.status,
        "progress": task.progress,
        "message": task.message,
        "result": task.result,
        "error": task.error,
        "created_at": task.created_at,
    }
