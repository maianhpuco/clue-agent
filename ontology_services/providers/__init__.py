"""Provider registries for the ontology MCP server."""

from .literature import LITERATURE_PROVIDERS, LiteratureSource
from .pathology import PATHOLOGY_PROVIDERS, PathologySource
from .terminology import ONTOLOGY_PROVIDERS, OntologySource

__all__ = [
    "LITERATURE_PROVIDERS",
    "PATHOLOGY_PROVIDERS",
    "ONTOLOGY_PROVIDERS",
    "LiteratureSource",
    "PathologySource",
    "OntologySource",
]
