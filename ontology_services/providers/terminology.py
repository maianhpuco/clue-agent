"""Ontology and terminology provider stubs."""

from __future__ import annotations

from typing import Dict, List, Literal

from .base import ProviderFunc, mock_result

OntologySource = Literal[
    "ncbo_bioportal",
    "ebi_ols",
    "nci_thesaurus",
    "snomed_ct",
    "mesh",
    "icd_o_3",
]


def search_ncbo_bioportal(query: str, max_results: int) -> List[Dict[str, str]]:
    return [
        mock_result(
            f"NCBO BioPortal aggregated ontology hit for {query}",
            "https://bioportal.bioontology.org/",
            "2023-05-14",
            "Varies",
            f"BioPortal entry aggregating definitions, synonyms, and hierarchical relations for {query}.",
        )
    ][:max_results]


def search_ebi_ols(query: str, max_results: int) -> List[Dict[str, str]]:
    return [
        mock_result(
            f"EBI Ontology Lookup Service match for {query}",
            "https://www.ebi.ac.uk/ols4/",
            "2022-09-09",
            "Varies",
            f"OLS provides cross-ontology lookup with NCIT, UBERON, and HPO context around {query}.",
        )
    ][:max_results]


def search_nci_thesaurus(query: str, max_results: int) -> List[Dict[str, str]]:
    return [
        mock_result(
            f"NCI Thesaurus preferred concept for {query}",
            "https://ncit.nci.nih.gov/",
            "2021-03-27",
            "CC-BY",
            f"NCIT concept detail including definitions, synonyms, and codes aligned with {query}.",
        )
    ][:max_results]


def search_snomed_ct(query: str, max_results: int) -> List[Dict[str, str]]:
    return [
        mock_result(
            f"SNOMED CT concept relationships for {query}",
            "https://browser.ihtsdotools.org/",
            "2024-02-11",
            "SNOMED International",
            f"SNOMED CT browser relationships linking {query} to morphology, finding sites, and procedures.",
        )
    ][:max_results]


def search_mesh(query: str, max_results: int) -> List[Dict[str, str]]:
    return [
        mock_result(
            f"MeSH tree placement for {query}",
            "https://meshb.nlm.nih.gov/",
            "2015-06-06",
            "U.S. Government",
            f"MeSH heading with entry terms and tree numbers illustrating where {query} fits in the hierarchy.",
        )
    ][:max_results]


def search_icdo3(query: str, max_results: int) -> List[Dict[str, str]]:
    return [
        mock_result(
            f"ICD-O-3 morphology/topography codes for {query}",
            "https://seer.cancer.gov/icd-o-3/",
            "2013-04-02",
            "U.S. Government",
            f"ICD-O-3 code mapping showing morphology and topography assignments relevant to {query}.",
        )
    ][:max_results]


ONTOLOGY_PROVIDERS: Dict[str, ProviderFunc] = {
    "ncbo_bioportal": search_ncbo_bioportal,
    "ebi_ols": search_ebi_ols,
    "nci_thesaurus": search_nci_thesaurus,
    "snomed_ct": search_snomed_ct,
    "mesh": search_mesh,
    "icd_o_3": search_icdo3,
}

__all__ = ["OntologySource", "ONTOLOGY_PROVIDERS"]
