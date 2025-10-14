"""
Stub connector for UMLS search.
"""
from typing import List, Dict

def search_umls(keyword: str, max_results: int = 2) -> List[Dict]:
    """
    Simulate UMLS search. Replace with real API call.
    Returns a list of dicts with 'concept', 'definition', 'cui'.
    """
    # TODO: Integrate with UMLS API
    return [
        {
            "concept": keyword,
            "definition": f"UMLS definition for {keyword}...",
            "cui": f"CUI_{i}_{keyword}"
        }
        for i in range(max_results)
    ]
