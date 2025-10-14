import os
from typing import List, Dict, Any, Optional
from openai import OpenAI


class LLMClient:
	def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None):
		api_key = os.getenv("OPENAI_API_KEY")
		if not api_key:
			raise RuntimeError("OPENAI_API_KEY not set")
		self.client = OpenAI(api_key=api_key, base_url=base_url or os.getenv("OPENAI_BASE_URL"))
		self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

	async def complete_json(self, system_prompt: str, user_prompt: str) -> str:
		# Use responses API to encourage JSON; avoid tool calling here.
		resp = self.client.chat.completions.create(
			model=self.model,
			messages=[
				{"role": "system", "content": system_prompt},
				{"role": "user", "content": user_prompt},
			],
			temperature=0.2,
		)
		return resp.choices[0].message.content or ""
