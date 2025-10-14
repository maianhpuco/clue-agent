"""
Stub connector for Wikipedia search.
"""
from typing import List, Dict

def search_wikipedia(keyword: str, max_results: int = 3) -> List[Dict]:
    """
    Simulate Wikipedia search. Replace with real API call.
    Returns a list of dicts with 'title', 'summary', 'url'.
    """
    # TODO: Integrate with Wikipedia API
    return [
        {
            "title": f"Wikipedia: {keyword}",
            "summary": f"Summary about {keyword}...",
            "url": f"https://en.wikipedia.org/wiki/{keyword.replace(' ', '_')}"
        }
        for _ in range(max_results)
    ]
