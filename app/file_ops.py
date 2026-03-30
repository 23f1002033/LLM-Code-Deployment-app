"""
Local filesystem operations for generated code and attachments.
"""

import os
import re
import base64
import logging
from typing import List

import httpx

from app.models import Attachment

log = logging.getLogger("deployment_service")

WORKSPACE_DIR = os.path.join(os.getcwd(), "generated_tasks")


def ensure_dir(path: str) -> None:
    """Create directory (and parents) if it doesn't exist."""
    os.makedirs(path, exist_ok=True)


def get_task_dir(task_id: str) -> str:
    """Return the local workspace path for a given task."""
    path = os.path.join(WORKSPACE_DIR, task_id)
    ensure_dir(path)
    return path


def save_generated_files(task_dir: str, files: dict) -> None:
    """Write generated code files to the task directory."""
    for filename, content in files.items():
        filepath = os.path.join(task_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        log.info("  Saved: %s (%d bytes)", filename, len(content))


async def save_attachments(
    task_dir: str, attachments: List[Attachment]
) -> List[str]:
    """
    Download and save task attachments to the local directory.
    Returns a list of successfully saved filenames.
    """
    saved = []
    if not attachments:
        return saved

    log.info("Processing %d attachment(s)", len(attachments))
    async with httpx.AsyncClient(timeout=30) as client:
        for att in attachments:
            if not att.name or not att.url:
                continue

            try:
                raw_bytes = None
                if att.url.startswith("data:"):
                    match = re.search(r"base64,(.*)", att.url, re.IGNORECASE)
                    if match:
                        raw_bytes = base64.b64decode(match.group(1))
                elif att.url.startswith(("http://", "https://")):
                    resp = await client.get(att.url)
                    resp.raise_for_status()
                    raw_bytes = resp.content

                if raw_bytes is None:
                    log.warning("No content for attachment: %s", att.name)
                    continue

                filepath = os.path.join(task_dir, att.name)
                with open(filepath, "wb") as f:
                    f.write(raw_bytes)
                saved.append(att.name)
                log.info("  Saved attachment: %s (%d bytes)", att.name, len(raw_bytes))
            except Exception as exc:
                log.error("Failed to save attachment %s: %s", att.name, exc)

    return saved


def read_existing_file(task_dir: str, filename: str) -> str:
    """Read an existing file from the task dir, or return empty string."""
    path = os.path.join(task_dir, filename)
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as exc:
        log.warning("Could not read %s: %s", filename, exc)
        return ""
