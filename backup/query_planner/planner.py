"""
Query Planner: Decides sources and keywords for definition search.
"""
from typing import List, Tuple, Optional

# Supported sources for definition search
SOURCES = ["pubmed", "wikipedia", "umls"]

def plan_sources_and_keywords(
    target: str,
    dataset: Optional[str] = None,
    class_names: Optional[List[str]] = None,
    user_query: Optional[str] = None,
) -> List[Tuple[str, str]]:
    """
    Decide which sources and keywords to use for definition search.
    Returns a list of (source, keyword) pairs.
    """
    # 1. Decide sources
    sources = []
    if dataset and dataset.lower() in ["camelyon16", "biomedical", "pathology"]:
        sources.append("pubmed")
        sources.append("umls")
    else:
        sources.append("wikipedia")
        sources.append("pubmed")

    # 2. Decide keywords
    base_terms = []
    if user_query:
        base_terms.append(user_query)
    if class_names:
        base_terms.extend(class_names)
    if target:
        base_terms.append(target)
    
    # Remove duplicates, preserve order
    seen = set()
    base_terms = [x for x in base_terms if not (x in seen or seen.add(x))]

    # 3. Generate keyword phrases
    keyword_templates = [
        "definition of {term}",
        "{term} is defined as",
        "what is {term}",
        "meaning of {term}",
        "{term} definition",
    ]
    pairs = []
    for source in sources:
        for term in base_terms:
            for template in keyword_templates:
                keyword = template.format(term=term)
                pairs.append((source, keyword))
    return pairs
