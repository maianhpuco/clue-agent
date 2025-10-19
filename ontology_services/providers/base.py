"""Shared helpers for provider implementations."""

from __future__ import annotations

import textwrap
from typing import Any, Callable, Dict, List

ProviderFunc = Callable[[str, int], List[Dict[str, Any]]]


def mock_result(title: str, url: str, published: str, license_: str, snippet: str) -> Dict[str, Any]:
    return {
        "title": title,
        "url": url,
        "published": published,
        "license": license_,
        "snippet": textwrap.shorten(snippet, width=280),
    }


__all__ = ["ProviderFunc", "mock_result"]
