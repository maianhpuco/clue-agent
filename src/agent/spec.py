from typing import List, Literal
from pydantic import BaseModel, Field, ValidationError
import json

ConceptType = Literal["class", "compartment", "morphology", "interface", "substructure"]


class ConceptItem(BaseModel):
	name: str
	definition: str
	synonyms: List[str] = Field(default_factory=list)
	concept_type: ConceptType
	positives: List[str]
	negatives: List[str]
	magnifications: List[Literal["10x", "20x", "40x"]]

	class Config:
		extra = "forbid"


def validate_concepts_json(text: str) -> List[ConceptItem]:
	"""Validate JSON text against the required schema and return parsed items.

	Raises ValidationError if invalid, including detailed error locations.
	"""
	data = json.loads(text)
	if not isinstance(data, list):
		raise ValidationError([{"loc": ("root",), "msg": "Expected a JSON array", "type": "type_error.list"}], ConceptItem)  # type: ignore[arg-type]
	items: List[ConceptItem] = []
	for idx, obj in enumerate(data):
		item = ConceptItem.model_validate(obj)
		# Basic cardinality checks aligned with guidance
		if len(item.positives) < 3 or len(item.negatives) < 3:
			raise ValidationError([{"loc": (idx, "positives/negatives"), "msg": "Require at least 3 positives and 3 negatives", "type": "value_error"}], ConceptItem)  # type: ignore[arg-type]
		items.append(item)
	return items


def concepts_to_json(items: List[ConceptItem]) -> str:
	return json.dumps([i.model_dump(mode="json") for i in items], ensure_ascii=False, indent=2)
