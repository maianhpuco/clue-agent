"""
Stub connector for PubMed search.
"""
from typing import List, Dict

def search_pubmed(keyword: str, max_results: int = 5) -> List[Dict]:
    """
    Simulate PubMed search. Replace with real API call.
    Returns a list of dicts with 'title', 'abstract', 'pmid'.
    """
    # TODO: Integrate with Entrez or other PubMed API
    # For now, return dummy data
    return [
        {
            "title": f"Dummy PubMed result for {keyword}",
            "abstract": f"Abstract about {keyword}...",
            "pmid": f"PMID_{i}_{keyword}"
        }
        for i in range(max_results)
    ]
