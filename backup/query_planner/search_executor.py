"""
Search Executor: Runs search for each (source, keyword) pair using the appropriate connector.
"""
from typing import List, Tuple, Dict
from ..source_connectors import pubmed, wikipedia, umls

def execute_search(pairs: List[Tuple[str, str]], max_results: int = 5) -> List[Dict]:
    """
    For each (source, keyword) pair, fetch candidate entries.
    Returns a list of dicts with source, keyword, and results.
    """
    all_results = []
    for source, keyword in pairs:
        if source == "pubmed":
            results = pubmed.search_pubmed(keyword, max_results)
        elif source == "wikipedia":
            results = wikipedia.search_wikipedia(keyword, max_results)
        elif source == "umls":
            results = umls.search_umls(keyword, max_results)
        else:
            results = []
        all_results.append({
            "source": source,
            "keyword": keyword,
            "results": results
        })
    return all_results
