"""Ontology tree construction and versioning utilities."""

from __future__ import annotations

import datetime as dt
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .db import list_extractions
from .settings import STORE_ROOT

BASE_ONTOLOGY_TREE: List[Dict[str, Any]] = [
    {
        "name": "Tumor",
        "definition": "Malignant epithelial proliferation/metastasis.",
        "synonyms": ["carcinoma", "metastasis"],
        "concept_type": "class",
        "positives": [
            "cohesive epithelial islands",
            "nuclear atypia",
            "mitoses",
            "peripheral palisading",
        ],
        "negatives": ["adipocytes", "dense collagen stroma", "lymphoid follicles"],
        "magnifications": ["20x", "40x"],
    },
    {
        "name": "Normal",
        "definition": "Non-neoplastic tissue compartments.",
        "synonyms": ["benign"],
        "concept_type": "class",
        "positives": [
            "ordered lymphoid follicles",
            "mature adipocytes",
            "regular stromal collagen",
        ],
        "negatives": ["malignant epithelial clusters", "necrosis"],
        "magnifications": ["10x", "20x"],
    },
]

VERSIONS_DIR = STORE_ROOT / "ontology_versions"


def _normalize_concepts(extraction_payload: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(extraction_payload, dict):
        return [extraction_payload]
    if isinstance(extraction_payload, list):
        return [item for item in extraction_payload if isinstance(item, dict)]
    return []


def build_ontology_tree(include_base: bool = True) -> List[Dict[str, Any]]:
    """Combine the base ontology tree with extracted concepts from the database."""
    tree: List[Dict[str, Any]] = []
    if include_base:
        tree.extend(deepcopy(BASE_ONTOLOGY_TREE))

    for record in list_extractions():
        extraction = (record.get("content") or {}).get("extraction")
        for concept in _normalize_concepts(extraction):
            tree.append(concept)
    return tree


def save_ontology_tree(
    tree: List[Dict[str, Any]],
    version_name: Optional[str] = None,
    ensure_suffix: bool = True,
) -> Path:
    """Persist the provided tree to the ontology_versions directory."""
    VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
    if version_name:
        filename = version_name
    else:
        timestamp = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        filename = f"ontology_{timestamp}.json"
    if ensure_suffix and not filename.endswith(".json"):
        filename = f"{filename}.json"
    target = VERSIONS_DIR / filename
    with target.open("w", encoding="utf-8") as handle:
        json.dump(tree, handle, indent=2, ensure_ascii=False)
    return target


def build_and_save_tree(
    include_base: bool = True,
    version_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Construct the ontology tree and write a versioned JSON snapshot to disk."""
    tree = build_ontology_tree(include_base=include_base)
    path = save_ontology_tree(tree, version_name=version_name)
    return {
        "status": "ok",
        "include_base": include_base,
        "version_path": str(path),
        "concept_count": len(tree),
        "version_name": path.name,
    }


__all__ = ["build_ontology_tree", "save_ontology_tree", "build_and_save_tree", "BASE_ONTOLOGY_TREE"]
