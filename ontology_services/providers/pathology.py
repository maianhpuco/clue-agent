"""Pathology reference provider stubs."""

from __future__ import annotations

from typing import Dict, List, Literal

from .base import ProviderFunc, mock_result

PathologySource = Literal[
    "pathology_outlines",
    "stanford_surgical_pathology_criteria",
    "libre_pathology",
    "cap_protocols",
]


def search_pathology_outlines(query: str, max_results: int) -> List[Dict[str, str]]:
    return [
        mock_result(
            f"Pathology Outlines quick facts on {query}",
            "https://www.pathologyoutlines.com/",
            "2024-01-05",
            "Website terms",
            f"Bullet-point morphology, diagnostic clues, and artifacts relevant to {query}.",
        )
    ][:max_results]


def search_stanford_criteria(query: str, max_results: int) -> List[Dict[str, str]]:
    return [
        mock_result(
            f"Stanford Surgical Pathology checklist for {query}",
            "https://surgpathcriteria.stanford.edu/",
            "2016-09-22",
            "Website terms",
            f"Structured gross and microscopic reporting criteria with key differentials for {query}.",
        )
    ][:max_results]


def search_libre_pathology(query: str, max_results: int) -> List[Dict[str, str]]:
    return [
        mock_result(
            f"Libre Pathology synopsis of {query}",
            "https://librepathology.org/wiki/Main_Page",
            "2020-07-30",
            "CC-BY-SA",
            f"Community maintained summary including synonyms, histology pearls, and pitfalls tied to {query}.",
        )
    ][:max_results]


def search_cap_protocols(query: str, max_results: int) -> List[Dict[str, str]]:
    return [
        mock_result(
            f"CAP protocol references for {query}",
            "https://www.cap.org/",
            "2021-12-01",
            "CAP copyright",
            f"College of American Pathologists protocol guidance with standardized terminology for {query}.",
        )
    ][:max_results]


PATHOLOGY_PROVIDERS: Dict[str, ProviderFunc] = {
    "pathology_outlines": search_pathology_outlines,
    "stanford_surgical_pathology_criteria": search_stanford_criteria,
    "libre_pathology": search_libre_pathology,
    "cap_protocols": search_cap_protocols,
}

__all__ = ["PathologySource", "PATHOLOGY_PROVIDERS"]
