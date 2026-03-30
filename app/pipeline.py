"""
Core orchestration pipeline.

Coordinates the full task lifecycle:
  1. Prepare local workspace and git repo
  2. Call the LLM for code generation
  3. Commit to GitHub and deploy via Pages
  4. Notify the evaluation server with results
"""

import os
import asyncio
import logging

from app.config import settings, flush_log_handlers
from app.models import TaskRequest, TaskRecord
from app import llm, github_ops, file_ops, notifier

log = logging.getLogger("deployment_service")


# task state management (in-memory, keyed by task_id)
_task_records: dict[str, TaskRecord] = {}
_task_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    """Lazy-init the concurrency limiter."""
    global _task_semaphore
    if _task_semaphore is None:
        _task_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_TASKS)
    return _task_semaphore


def get_task_records() -> list[TaskRecord]:
    """All tracked tasks, most recent first."""
    return sorted(
        _task_records.values(),
        key=lambda r: r.received_at,
        reverse=True,
    )


def get_active_count() -> int:
    """Number of tasks currently being processed."""
    return sum(1 for r in _task_records.values() if r.status == "processing")


def record_task(req: TaskRequest) -> TaskRecord:
    """Create and store a tracking record for an incoming task."""
    record = TaskRecord.from_request(req)
    _task_records[record.task_id] = record
    return record


async def run_pipeline(task_data: TaskRequest) -> None:
    """
    Main pipeline execution.
    Acquires a semaphore slot, runs the full generate-deploy cycle,
    and updates the task record with the outcome.
    """
    sem = _get_semaphore()
    record = _task_records.get(task_data.task)
    acquired = False

    try:
        log.info("Task %s waiting for available slot...", task_data.task)
        await sem.acquire()
        acquired = True

        if record:
            record.status = "processing"

        task_id = task_data.task
        round_index = task_data.round
        repo_name = task_id.replace(" ", "-").lower()

        log.info("--- Pipeline START: %s (round %d) ---", task_id, round_index)
        flush_log_handlers()

        # 1. prepare workspace
        task_dir = file_ops.get_task_dir(task_id)
        if os.path.exists(task_dir):
            github_ops.cleanup_directory(task_dir)
        file_ops.ensure_dir(task_dir)

        # 2. setup git repo
        repo = await github_ops.setup_repo(task_dir, repo_name, round_index)

        # 3. process image attachments for LLM context
        image_parts = []
        attachment_note = ""
        if task_data.attachments:
            for att in task_data.attachments:
                part = await llm.attachment_to_gemini_part(att.url)
                if part:
                    image_parts.append(part)

            attachment_note = "\nAttached files (use exact filenames in HTML):\n"
            for att in task_data.attachments:
                attachment_note += f"- {att.name}\n"

        enriched_brief = f"{task_data.brief}\n{attachment_note}".strip()

        # 4. generate code
        if round_index == 1:
            log.info("Round 1: full generation")
            generated = await llm.generate_round1(enriched_brief, image_parts)
        else:
            log.info("Round %d: surgical update", round_index)
            existing_html = file_ops.read_existing_file(task_dir, "index.html")
            generated = await llm.generate_round2(enriched_brief, existing_html)

            # keep existing README/LICENSE if LLM returned empty
            if not generated.get("README.md"):
                generated["README.md"] = file_ops.read_existing_file(task_dir, "README.md")
            if not generated.get("LICENSE"):
                generated["LICENSE"] = file_ops.read_existing_file(task_dir, "LICENSE")

        # 5. save generated files + attachments
        file_ops.save_generated_files(task_dir, generated)
        await file_ops.save_attachments(task_dir, task_data.attachments)

        # 6. commit, push, configure Pages
        deploy_info = await github_ops.commit_and_deploy(
            repo, task_id, round_index, repo_name
        )

        # 7. notify evaluation server
        await notifier.notify_evaluation_server(
            evaluation_url=task_data.evaluation_url,
            email=task_data.email,
            task_id=task_id,
            round_index=round_index,
            nonce=task_data.nonce,
            repo_url=deploy_info["repo_url"],
            commit_sha=deploy_info["commit_sha"],
            pages_url=deploy_info["pages_url"],
        )

        if record:
            record.status = "done"
            record.pages_url = deploy_info["pages_url"]
            record.repo_url = deploy_info["repo_url"]

        log.info(
            "--- Pipeline COMPLETE: %s | %s ---",
            task_id, deploy_info["pages_url"],
        )

    except Exception as exc:
        log.exception("Pipeline FAILED for %s: %s", task_data.task, exc)
        if record:
            record.status = "failed"
            record.error_message = str(exc)[:500]
    finally:
        if acquired:
            sem.release()
        flush_log_handlers()
