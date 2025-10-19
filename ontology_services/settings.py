"""Configuration helpers for the ontology MCP server."""

from __future__ import annotations

import os
from pathlib import Path

DATASET = os.environ.get("DATASET_NAME", "Camelyon16")
STORE_ROOT = Path(os.environ.get("ONTOLOGY_DOC_DIR", "documents"))

__all__ = ["DATASET", "STORE_ROOT"]
