"""
Example usage of query planner - demonstrates planning logic without requiring full PubMed setup.
"""
import json
from pathlib import Path
from typing import List, Dict, Any

from .planner import plan_sources_and_keywords


def run_query_planner_example():
    """Example: Plan queries for Camelyon16 concepts (demo version)."""
    
    # 1. Plan queries for Camelyon16 concepts
    print("=== Query Planning Demo ===")
    target_concepts = ["tumor", "normal", "lymph node", "metastasis", "carcinoma"]
    
    all_planned_queries = []
    for concept in target_concepts:
        pairs = plan_sources_and_keywords(
            target=concept,
            dataset="Camelyon16",
            class_names=["Tumor", "Normal"],
            user_query=f"{concept} pathology"
        )
        # Extract just the keywords for PubMed
        pubmed_keywords = [keyword for source, keyword in pairs if source == "pubmed"]
        all_planned_queries.extend(pubmed_keywords[:3])  # Limit to 3 per concept
    
    print(f"Planned {len(all_planned_queries)} PubMed queries:")
    for i, query in enumerate(all_planned_queries, 1):
        print(f"  {i}. {query}")
    
    # 2. Save results
    output_dir = Path("outputs/query_planner_example")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save planned queries
    (output_dir / "planned_queries.json").write_text(
        json.dumps(all_planned_queries, indent=2), encoding="utf-8"
    )
    
    print(f"\n=== Results Saved ===")
    print(f"Planned queries: {output_dir / 'planned_queries.json'}")
    print(f"\nNote: To execute these queries with PubMed, use the main pipeline:")
    print(f"  make create_concept")


def show_planning_strategy():
    """Show how the planner works for different scenarios."""
    print("=== Query Planning Strategy Examples ===")
    
    scenarios = [
        {
            "name": "Camelyon16 Tumor",
            "target": "tumor",
            "dataset": "Camelyon16", 
            "class_names": ["Tumor", "Normal"],
            "user_query": "lymph node metastasis"
        },
        {
            "name": "General Pathology",
            "target": "necrosis",
            "dataset": "General",
            "class_names": ["Necrosis"],
            "user_query": None
        }
    ]
    
    for scenario in scenarios:
        print(f"\n--- {scenario['name']} ---")
        # Remove 'name' before passing to function
        scenario_params = {k: v for k, v in scenario.items() if k != "name"}
        pairs = plan_sources_and_keywords(**scenario_params)
        
        # Group by source
        by_source = {}
        for source, keyword in pairs:
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(keyword)
        
        for source, keywords in by_source.items():
            print(f"  {source.upper()}:")
            for keyword in keywords[:3]:  # Show first 3
                print(f"    - {keyword}")
            if len(keywords) > 3:
                print(f"    ... and {len(keywords) - 3} more")


if __name__ == "__main__":
    print("Query Planner Example")
    print("=" * 50)
    
    # Show planning strategy
    show_planning_strategy()
    
    # Run the demo example
    print("\n" + "=" * 50)
    run_query_planner_example()
