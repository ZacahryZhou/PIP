"""Small helpers shared by fal.ai providers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx


def require_fal_client(api_key: str):
    """Import fal_client lazily so mock/test runs do not require network deps."""
    if not api_key:
        raise ValueError("FAL_KEY is required for real fal.ai generation.")
    os.environ["FAL_KEY"] = api_key
    try:
        import fal_client
    except ImportError as exc:  # pragma: no cover - exercised in real env only
        raise RuntimeError(
            "fal-client is required for real generation. "
            "Install the project dependencies, then retry."
        ) from exc
    return fal_client


def first_url(payload: Any, *, preferred_exts: tuple[str, ...]) -> str:
    """Find the first URL in a nested fal response, preferring media extensions."""
    urls: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            urls.append(value)
            return
        if isinstance(value, dict):
            for nested in value.values():
                visit(nested)
            return
        if isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(payload)
    if not urls:
        raise RuntimeError(f"No downloadable URL found in fal response: {payload!r}")

    for url in urls:
        path = urlparse(url).path.lower()
        if path.endswith(preferred_exts):
            return url
    return urls[0]


def download_url(url: str, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        output_path.write_bytes(response.content)
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError(f"Downloaded empty media file from {url}")
    return output_path


def request_id_from(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get("request_id") or payload.get("requestId")
    return str(value) if value else None
