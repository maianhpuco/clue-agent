"""HTTP convenience helpers with retry/backoff for provider integrations."""

from __future__ import annotations

import json
import re
import time
from html import unescape
from typing import Any, Dict, Optional, Tuple

import httpx

DEFAULT_TIMEOUT: Tuple[float, float] = (6.0, 30.0)
USER_AGENT = "OntologyMCP/1.0 (+https://example.com) httpx"
HTML_TAG_RE = re.compile(r"<[^>]+>")


def _build_timeout(timeout: Tuple[float, float] | float | httpx.Timeout) -> httpx.Timeout:
    if isinstance(timeout, httpx.Timeout):
        return timeout
    if isinstance(timeout, tuple):
        connect, read = timeout
        return httpx.Timeout(read, connect=connect)
    return httpx.Timeout(float(timeout))


def strip_html(value: str) -> str:
    """Remove simple HTML tags and entities from provider snippets."""
    return HTML_TAG_RE.sub(" ", unescape(value or ""))


def http_get(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: Tuple[float, float] | float | httpx.Timeout = DEFAULT_TIMEOUT,
    retries: int = 2,
) -> Any:
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    timeout_config = _build_timeout(timeout)
    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            response = httpx.get(url, params=params, headers=request_headers, timeout=timeout_config)
            if response.status_code == 429 and attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "json" in content_type:
                return response.json()
            try:
                return response.json()
            except (ValueError, json.JSONDecodeError):
                return response.text
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(1.0 * (attempt + 1))
                continue
            break
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("http_get failed without raising an exception.")


__all__ = ["DEFAULT_TIMEOUT", "USER_AGENT", "strip_html", "http_get"]
