"""
GitHub repository and Pages management.

Handles repo creation, cloning, committing, pushing,
and configuring GitHub Pages for automated deployment.
"""

import os
import stat
import shutil
import asyncio
import logging

import git
import httpx

from app.config import settings

log = logging.getLogger("deployment_service")


def _github_headers() -> dict:
    """Standard headers for GitHub API calls."""
    return {
        "Authorization": f"token {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _auth_clone_url(repo_name: str) -> str:
    """Build an authenticated clone URL. This value should never be logged."""
    return (
        f"https://{settings.GITHUB_USERNAME}:{settings.GITHUB_TOKEN}"
        f"@github.com/{settings.GITHUB_USERNAME}/{repo_name}.git"
    )


def _public_repo_url(repo_name: str) -> str:
    """Public (non-authenticated) repo URL, safe for logging and display."""
    return f"https://github.com/{settings.GITHUB_USERNAME}/{repo_name}"


def cleanup_directory(path: str) -> None:
    """
    Remove a directory tree. Handles read-only files that
    git creates inside .git/ on some platforms.
    """
    if not os.path.exists(path):
        return

    def _force_remove(func, file_path, _exc_info):
        os.chmod(file_path, stat.S_IWUSR)
        func(file_path)

    log.info("Cleaning up directory: %s", path)
    shutil.rmtree(path, onerror=_force_remove)


async def setup_repo(
    local_path: str, repo_name: str, round_index: int
) -> git.Repo:
    """
    Prepare a local git repository for the task.

    Round 1: creates a new remote repo on GitHub, initializes locally.
    Round 2+: clones the existing repo.
    If a Round 1 repo already exists (422), falls back to cloning.
    """
    headers = _github_headers()
    auth_url = _auth_clone_url(repo_name)

    async with httpx.AsyncClient(timeout=45) as client:
        if round_index == 1:
            log.info("Creating GitHub repo: %s", repo_name)
            resp = await client.post(
                f"{settings.GITHUB_API_BASE}/user/repos",
                json={"name": repo_name, "private": False, "auto_init": True},
                headers=headers,
            )
            # repo might already exist from a previous attempt
            if resp.status_code == 422:
                log.info("Repo already exists — cloning instead")
                return git.Repo.clone_from(auth_url, local_path)
            resp.raise_for_status()

            repo = git.Repo.init(local_path)
            repo.create_remote("origin", auth_url)
            return repo
        else:
            log.info("Cloning repo for round %d: %s", round_index, repo_name)
            return git.Repo.clone_from(auth_url, local_path)


async def commit_and_deploy(
    repo: git.Repo,
    task_id: str,
    round_index: int,
    repo_name: str,
) -> dict:
    """
    Stage all changes, commit, push to main, and enable GitHub Pages.

    Returns a dict with repo_url, commit_sha, and pages_url.
    """
    headers = _github_headers()

    # commit and push
    repo.git.add(A=True)
    repo.index.commit(f"[{task_id}] round {round_index}: auto-deploy")
    sha = repo.head.object.hexsha[:8]
    log.info("Committed: %s", sha)

    repo.git.branch("-M", "main")
    repo.git.push("--set-upstream", "origin", "main", force=True)
    log.info("Pushed to origin/main")

    # enable GitHub Pages (retry loop for propagation delays)
    pages_api = (
        f"{settings.GITHUB_API_BASE}/repos/"
        f"{settings.GITHUB_USERNAME}/{repo_name}/pages"
    )
    pages_config = {"source": {"branch": "main", "path": "/"}}

    async with httpx.AsyncClient(timeout=45) as client:
        for attempt in range(5):
            try:
                check = await client.get(pages_api, headers=headers)
                if check.status_code == 200:
                    await client.put(pages_api, json=pages_config, headers=headers)
                else:
                    await client.post(pages_api, json=pages_config, headers=headers)
                log.info("GitHub Pages configured successfully")
                break
            except httpx.HTTPStatusError as exc:
                body = getattr(exc.response, "text", "")
                is_timing_issue = (
                    exc.response.status_code == 422
                    and "main branch must exist" in body
                )
                if is_timing_issue and attempt < 4:
                    delay = 3 * (2 ** attempt)
                    log.warning("Pages timing issue, retry in %ds", delay)
                    await asyncio.sleep(delay)
                    continue
                raise

    # allow a moment for Pages deployment to start
    await asyncio.sleep(5)

    return {
        "repo_url": _public_repo_url(repo_name),
        "commit_sha": sha,
        "pages_url": f"{settings.pages_base_url}/{repo_name}/",
    }
