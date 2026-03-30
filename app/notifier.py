"""
Evaluation server notification handler.

After deploying generated code, we POST the deployment details
back to the evaluation server so it can verify the result.
"""

import asyncio
import logging

import httpx

log = logging.getLogger("deployment_service")


async def notify_evaluation_server(
    evaluation_url: str,
    email: str,
    task_id: str,
    round_index: int,
    nonce: str,
    repo_url: str,
    commit_sha: str,
    pages_url: str,
    max_retries: int = 3,
) -> bool:
    """
    POST deployment results to the evaluation server.
    Retries with exponential backoff on failure.
    Returns True on success, False if all attempts fail.
    """
    payload = {
        "email": email,
        "task": task_id,
        "round": round_index,
        "nonce": nonce,
        "repo_url": repo_url,
        "commit_sha": commit_sha,
        "pages_url": pages_url,
    }

    log.info("Notifying evaluation server at %s", evaluation_url)

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(evaluation_url, json=payload)
                resp.raise_for_status()
            log.info("Notification successful (HTTP %d)", resp.status_code)
            return True
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            log.warning(
                "Notification attempt %d/%d failed: %s",
                attempt + 1, max_retries, exc,
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)

    log.error("All notification attempts failed for task %s", task_id)
    return False
