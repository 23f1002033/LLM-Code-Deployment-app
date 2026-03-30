"""
Configuration management.

All sensitive values are sourced from environment variables
or an .env file — nothing is hardcoded here.
"""

import os
import sys
import logging
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration. Reads from env vars or .env file."""

    # credentials (set via HF Space Secrets or .env)
    GEMINI_API_KEY: str = Field("", env="GEMINI_API_KEY")
    GITHUB_TOKEN: str = Field("", env="GITHUB_TOKEN")
    GITHUB_USERNAME: str = Field("", env="GITHUB_USERNAME")
    STUDENT_SECRET: str = Field("", env="STUDENT_SECRET")

    # app behaviour
    LOG_FILE_PATH: str = Field("logs/app.log", env="LOG_FILE_PATH")
    MAX_CONCURRENT_TASKS: int = Field(2, env="MAX_CONCURRENT_TASKS")
    KEEP_ALIVE_INTERVAL: int = Field(30, env="KEEP_ALIVE_INTERVAL_SECONDS")

    # external services
    GITHUB_API_BASE: str = Field("https://api.github.com", env="GITHUB_API_BASE")
    GITHUB_PAGES_BASE: Optional[str] = None
    GEMINI_MODEL: str = Field(
        "gemini-2.5-flash-preview-05-20", env="GEMINI_MODEL"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def pages_base_url(self) -> str:
        if self.GITHUB_PAGES_BASE:
            return self.GITHUB_PAGES_BASE
        return f"https://{self.GITHUB_USERNAME}.github.io"

    @property
    def gemini_endpoint(self) -> str:
        return (
            "https://generativelanguage.googleapis.com/v1beta/"
            f"models/{self.GEMINI_MODEL}:generateContent"
        )


settings = Settings()


# --------------- Logging ---------------

def setup_logging() -> logging.Logger:
    """Configure dual-output logging (console + file)."""
    os.makedirs(os.path.dirname(settings.LOG_FILE_PATH), exist_ok=True)

    logger = logging.getLogger("deployment_service")
    logger.setLevel(logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)

    fh = logging.FileHandler(settings.LOG_FILE_PATH, mode="a", encoding="utf-8")
    fh.setFormatter(fmt)

    logger.handlers = []
    logger.addHandler(console)
    logger.addHandler(fh)
    logger.propagate = False
    return logger


log = setup_logging()


def flush_log_handlers():
    """Force-flush all log handlers — useful before process exit."""
    try:
        sys.stdout.flush()
        sys.stderr.flush()
        for h in log.handlers:
            try:
                h.flush()
            except Exception:
                pass
    except Exception:
        pass
