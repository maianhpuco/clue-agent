#!/usr/bin/env python3
"""
MCP Server: Ontology Builder (stdio transport)
Generates ontology-ready concept JSON from class descriptions, validates, and persists.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from typing import Any, Dict, List, Tuple

# FastMCP runtime
try:
    from fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - ensures helpful error when dependency missing
        raise SystemExit("fastmcp is not installed. Run: pip install fastmcp") from exc

DATA_ROOT = os.environ.get("ONTOLOGY_DATA_ROOT", "ontology_data")

mcp = FastMCP("ontology_builder")

# ----------------------------
# LLM stub (plug your model)
# ----------------------------
def call_llm(prompt: str, model: str = "gpt-4o-mini", temperature: float = 0.2) -> str:
    """
    Return STRICT JSON (string). Replace with your provider call.
    - Must return a JSON array of items with the exact fields required.
    """
    # TODO: Plug in OpenAI/Anthropic/local call here and return raw text.
    # For now, we return a tiny, schema-correct seed to keep the pipeline functional.
    seed = [
        {
            "name": "Tumor",
            "definition": "Malignant epithelial proliferation/metastasis in lymph node.",
            "synonyms": ["carcinoma", "metastasis"],
            "concept_type": "class",
            "positives": ["cohesive epithelial islands", "nuclear atypia", "mitoses"],
            "negatives": ["ordered lymphoid follicles", "adipocytes", "dense collagen stroma"],
            "magnifications": ["20x", "40x"],
        },
        {
            "name": "Normal",
            "definition": "Non-neoplastic nodal compartments with preserved architecture.",
            "synonyms": ["benign"],
            "concept_type": "class",
            "positives": ["germinal centers", "sinus histiocytes", "regular stromal collagen"],
            "negatives": ["malignant epithelial clusters", "necrosis"],
            "magnifications": ["10x", "20x"],
        },
    ]
    return json.dumps(seed, indent=2)


# ----------------------------
# Prompt builder
# ----------------------------
def build_prompt(dataset_name: str, class_desc_json: str, num_classes_hint: int | None = None) -> str:
    try:
        class_descriptions = json.loads(class_desc_json)
    except json.JSONDecodeError:
        class_descriptions = {"_raw": class_desc_json}

    num_classes = num_classes_hint or (
        len(class_descriptions) if isinstance(class_descriptions, dict) else None
    )
    class_blob = json.dumps(class_descriptions, indent=2, ensure_ascii=False)

    return f"""
Role
You are a board-certified pathologist. The dataset is "{dataset_name}",
which has {num_classes} high-level class(es).

Dataset class descriptions
The following short descriptions summarize the dataset classes and what constitutes positives/negatives. Use them to anchor definitions and include commonly confused morphologies.

{class_blob}

Goal
For each high-level class, enumerate the key pathology morphology concepts
that commonly appear in slide patches (and those that are commonly confused
with them). Include the magnification levels (10x, 20x, 40x) at which each
concept is best recognized.

Return format
OUTPUT JSON ONLY (no prose, no markdown). Return a JSON array where each
item has EXACTLY these fields:

- name
- definition
- synonyms
- concept_type              # one of ["class","compartment","morphology","interface","substructure"]
- positives                 # list[str], 3–6 patch-scale cues present
- negatives                 # list[str], 3–6 patch-scale confounders/exclusions
- magnifications            # list[str] from ["10x","20x","40x"]

Guidance
- Keep medical wording concise and specific (no narrative).
- Positives/negatives are patch-scale cues (not diagnoses).
- Include compartments (e.g., stroma, lymphoid tissue), morphologies (e.g., tumor nests, necrosis),
  and interfaces (e.g., tumor–stroma interface).
- If a concept is recognized at multiple magnifications, list them all.

Camelyon example concepts to ensure coverage when applicable:
- Normal (class), Tumor (class),
- Lymphoid tissue (compartment), Adipose tissue (compartment), Stroma (compartment),
- Tumor nest (morphology), Tumor–stroma interface (interface), Necrosis (morphology).

IMPORTANT
- Return STRICT JSON array only. No comments. No markdown. No trailing text.
"""


# ----------------------------
# Validation / normalization
# ----------------------------
ALLOWED_TYPES = {"class", "compartment", "morphology", "interface", "substructure"}
ALLOWED_MAGS = {"10x", "20x", "40x"}


def slugify(value: str) -> str:
    safe = []
    for ch in value:
        if ch.isalnum():
            safe.append(ch.lower())
        elif ch in "-_ ":
            safe.append("-")
        else:
            safe.append("-")
    return "-".join("".join(safe).split("-")) or "concept"


def validate_item(item: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    for field in ["name", "definition", "synonyms", "concept_type", "positives", "negatives", "magnifications"]:
        if field not in item:
            errors.append(f"Missing field: {field}")
    if "concept_type" in item and item["concept_type"] not in ALLOWED_TYPES:
        errors.append(f"concept_type must be one of {sorted(ALLOWED_TYPES)}")
    if "magnifications" in item:
        magnifications = set(item["magnifications"])
        if not magnifications.issubset(ALLOWED_MAGS):
            errors.append(f"magnifications must be subset of {sorted(ALLOWED_MAGS)}")
    for field in ["positives", "negatives"]:
        if field in item:
            values = item[field] or []
            if not (3 <= len(values) <= 6):
                errors.append(f"{field} must have 3–6 items")
    return (len(errors) == 0, errors)


def normalize_items(items: List[Dict[str, Any]], namespace: str) -> List[Dict[str, Any]]:
    seen_synonyms = set()
    normalized = []
    for item in items:
        synonyms = []
        for synonym in item.get("synonyms", []):
            cleaned = synonym.strip()
            lowered = cleaned.lower()
            if lowered and lowered not in seen_synonyms:
                synonyms.append(lowered)
                seen_synonyms.add(lowered)
        concept_id = f"{namespace}/{slugify(item['name'])}"
        normalized.append({**item, "synonyms": synonyms, "id": concept_id})
    return normalized


def persist_run(
    dataset_name: str, prompt: str, raw_json: str, validated: List[Dict[str, Any]]
) -> Dict[str, str]:
    dataset_dir = os.path.join(DATA_ROOT, dataset_name)
    os.makedirs(dataset_dir, exist_ok=True)

    run_dir = os.path.join(
        dataset_dir, "runs", dt.datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%SZ")
    )
    os.makedirs(run_dir, exist_ok=True)

    with open(os.path.join(run_dir, "prompt.txt"), "w", encoding="utf-8") as handle:
        handle.write(prompt)
    with open(os.path.join(run_dir, "raw_model.json"), "w", encoding="utf-8") as handle:
        handle.write(raw_json)

    concepts_path = os.path.join(dataset_dir, "concepts.json")
    with open(concepts_path, "w", encoding="utf-8") as handle:
        json.dump(validated, handle, indent=2, ensure_ascii=False)

    with open(os.path.join(run_dir, "validated.json"), "w", encoding="utf-8") as handle:
        json.dump(validated, handle, indent=2, ensure_ascii=False)

    ontology_path = os.path.join(dataset_dir, "ontology.json")
    ontology = {
        "concepts": [
            {"id": item["id"], "name": item["name"], "concept_type": item["concept_type"]}
            for item in validated
        ],
        "relations": [],
    }
    with open(ontology_path, "w", encoding="utf-8") as handle:
        json.dump(ontology, handle, indent=2, ensure_ascii=False)

    return {
        "concepts_path": concepts_path,
        "ontology_path": ontology_path,
        "run_dir": run_dir,
    }


# ----------------------------
# MCP tools
# ----------------------------
@mcp.tool()
def generate_concepts(dataset_name: str, class_descriptions_json: str, num_classes_hint: int = 0) -> str:
    """
    Generate schema-conformant concepts for a dataset.

    Args:
        dataset_name: e.g., "Camelyon16"
        class_descriptions_json: JSON string mapping classes -> descriptions
        num_classes_hint: optional integer

    Returns:
        STRICT JSON array (string) with required fields per item.
    """
    prompt = build_prompt(dataset_name, class_descriptions_json, num_classes_hint or None)
    raw = call_llm(prompt)
    return raw


@mcp.tool()
def validate_and_persist(dataset_name: str, concepts_json: str) -> str:
    """
    Validate, normalize, assign stable IDs, and persist artifacts.

    Args:
        dataset_name: e.g., "Camelyon16"
        concepts_json: JSON array string returned by generate_concepts

    Returns:
        JSON string with {"status","errors","paths","count"}
    """
    try:
        items = json.loads(concepts_json)
        assert isinstance(items, list)
    except Exception as exc:
        return json.dumps({"status": "error", "errors": [f"Invalid JSON array: {exc}"]}, indent=2)

    errors: List[str] = []
    for index, item in enumerate(items):
        ok, item_errors = validate_item(item)
        if not ok:
            errors.extend([f"item[{index}]: {error}" for error in item_errors])

    if errors:
        return json.dumps({"status": "invalid", "errors": errors}, indent=2)

    namespace = slugify(dataset_name)
    normalized = normalize_items(items, namespace=namespace)
    paths = persist_run(
        dataset_name,
        prompt="(omitted: see run/)",
        raw_json=concepts_json,
        validated=normalized,
    )
    return json.dumps({"status": "ok", "count": len(normalized), "paths": paths}, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
