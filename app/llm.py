"""
Gemini API integration for code generation.

Supports full generation (Round 1) and surgical updates (Round 2+),
including multimodal inputs when image attachments are present.
"""

import re
import json
import base64
import asyncio
import logging
from typing import Optional, List

import httpx

from app.config import settings

log = logging.getLogger("deployment_service")

# safety thresholds for round-2 output validation
_MIN_OUTPUT_LENGTH = 200
_MAX_SHRINKAGE_RATIO = 0.3


async def call_gemini(
    contents: list,
    system_prompt: str,
    response_schema: dict,
    max_retries: int = 3,
    timeout: int = 60,
) -> dict:
    """
    Send a structured generation request to the Gemini API.

    Uses the x-goog-api-key header instead of URL params to keep
    credentials out of access logs and proxy caches.
    """
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    payload = {
        "contents": contents,
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": response_schema,
        },
    }

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": settings.GEMINI_API_KEY,
    }

    last_error = None
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    settings.gemini_endpoint,
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()

                result = resp.json()
                candidates = result.get("candidates", [])
                if not candidates:
                    raise ValueError("Empty candidates list in Gemini response")

                text = (
                    candidates[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                )
                return json.loads(text)

        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            last_error = exc
            log.warning("Gemini HTTP error (attempt %d/%d): %s", attempt + 1, max_retries, exc)
        except (json.JSONDecodeError, ValueError, KeyError, IndexError) as exc:
            last_error = exc
            log.warning("Gemini parse error (attempt %d/%d): %s", attempt + 1, max_retries, exc)

        if attempt < max_retries - 1:
            delay = 2 ** attempt
            log.info("Retrying in %ds...", delay)
            await asyncio.sleep(delay)

    raise RuntimeError(f"Gemini API failed after {max_retries} attempts: {last_error}")


# ---- generation output schema ----
_FILE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "index.html": {"type": "STRING"},
        "README.md": {"type": "STRING"},
        "LICENSE": {"type": "STRING"},
    },
    "required": ["index.html", "README.md", "LICENSE"],
}


async def generate_round1(brief: str, image_parts: List[dict]) -> dict:
    """Full application generation from scratch (Round 1)."""
    system_prompt = (
        "You are a senior full-stack engineer. Generate a single-file responsive "
        "HTML application using Tailwind CSS from the CDN. Return a JSON object "
        "with keys 'index.html', 'README.md', and 'LICENSE'. The README should "
        "describe the project professionally. LICENSE should be MIT. If image "
        "attachments are referenced, use their exact filenames in <img> tags."
    )

    parts: list = []
    if image_parts:
        parts.extend(image_parts)
    parts.append({"text": brief})

    return await call_gemini(
        contents=[{"parts": parts}],
        system_prompt=system_prompt,
        response_schema=_FILE_SCHEMA,
        max_retries=4,
        timeout=120,
    )


async def generate_round2(brief: str, existing_html: str) -> dict:
    """
    Surgical update of existing application (Round 2+).
    Preserves core structure and only modifies what the brief asks for.
    """
    system_prompt = (
        "You are a senior full-stack engineer making targeted, minimal changes. "
        "CRITICAL: preserve the existing application's core logic, layout, and "
        "event handlers. Only modify what the brief explicitly asks for. Return "
        "full JSON with 'index.html', 'README.md', 'LICENSE'. Copy README/LICENSE "
        "verbatim unless a change is specifically required."
    )

    prompt = (
        f"UPDATE REQUEST:\n\n"
        f"Brief: {brief}\n\n"
        f"--- EXISTING index.html ---\n{existing_html}\n--- END ---\n\n"
        "Apply only the minimum changes needed. Do NOT rewrite sections "
        "unrelated to the brief."
    )

    try:
        result = await call_gemini(
            contents=[{"parts": [{"text": prompt}]}],
            system_prompt=system_prompt,
            response_schema=_FILE_SCHEMA,
            max_retries=4,
            timeout=90,
        )
    except Exception as exc:
        log.error("Round 2 generation failed, preserving original: %s", exc)
        return {
            "index.html": existing_html or "<!-- preserved due to generation failure -->",
            "README.md": "",
            "LICENSE": "",
        }

    # validate output isn't suspiciously small (possible destructive rewrite)
    new_html = (result.get("index.html") or "").strip()
    if not new_html:
        log.warning("LLM returned empty HTML, reverting to original")
        result["index.html"] = existing_html
    elif existing_html:
        orig_len = len(existing_html)
        threshold = max(_MIN_OUTPUT_LENGTH, int(orig_len * _MAX_SHRINKAGE_RATIO))
        if orig_len > 0 and len(new_html) < threshold:
            log.warning(
                "Output suspiciously small (%d vs %d chars), reverting",
                len(new_html), orig_len,
            )
            result["index.html"] = existing_html

    result.setdefault("README.md", "")
    result.setdefault("LICENSE", "")
    return result


# ---- attachment helpers ----

def parse_data_uri(data_uri: str) -> Optional[dict]:
    """Convert a base64 data URI into a Gemini inlineData part."""
    match = re.search(
        r"data:(?P<mime>[^;]+);base64,(?P<data>.*)", data_uri, re.IGNORECASE
    )
    if not match or not match.group("mime").startswith("image/"):
        return None
    return {
        "inlineData": {
            "data": match.group("data"),
            "mimeType": match.group("mime"),
        }
    }


async def fetch_image_as_part(url: str) -> Optional[dict]:
    """Download a remote image and wrap it as a Gemini multimodal part."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            mime = resp.headers.get("Content-Type", "")
            if not mime.startswith("image/"):
                log.info("Skipping non-image attachment (MIME: %s)", mime)
                return None
            b64 = base64.b64encode(resp.content).decode()
            return {"inlineData": {"data": b64, "mimeType": mime}}
    except Exception as exc:
        log.warning("Failed to fetch image attachment: %s", exc)
        return None


async def attachment_to_gemini_part(url: str) -> Optional[dict]:
    """Route an attachment URL to the appropriate converter."""
    if not url:
        return None
    if url.startswith("data:"):
        return parse_data_uri(url)
    if url.startswith(("http://", "https://")):
        return await fetch_image_as_part(url)
    return None
