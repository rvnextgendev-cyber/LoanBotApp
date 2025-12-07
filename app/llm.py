import json
from typing import Any

import httpx

from .config import settings


class LLMClient:
    """
    Minimal OpenAI-compatible chat client.
    Works with local LLaMA runtimes such as Ollama/llama.cpp that expose /v1/chat/completions.
    """

    def __init__(
        self, model: str | None = None, base_url: str | None = None, api_key: str | None = None
    ):
        self.model = model or settings.llm_model
        self.base_url = base_url or settings.llm_base_url or "http://localhost:11434/v1"
        self.api_key = api_key or settings.llm_api_key
        self.client = httpx.AsyncClient(timeout=60)

    async def chat(self, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions", json=payload, headers=headers
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception:
            # Fallback deterministic prompt for offline runs.
            return self._rule_based(messages)

    def _rule_based(self, messages: list[dict[str, str]]) -> str:
        """
        If the LLM endpoint is not reachable, respond with a deterministic JSON action.
        This keeps the agent loop testable without a model.
        """
        required = ["applicant_name", "applicant_email", "amount", "purpose"]
        collected: dict[str, Any] = {}
        # Try to read any inline JSON for tests; otherwise just ask for the first missing field.
        for msg in messages[::-1]:
            if msg["role"] == "user":
                try:
                    maybe = json.loads(msg["content"])
                    if isinstance(maybe, dict):
                        collected = maybe
                except json.JSONDecodeError:
                    pass
                break

        missing = [f for f in required if f not in collected]
        if missing:
            question_map = {
                "applicant_name": "What is the applicant name?",
                "applicant_email": "What's the best email to reach you?",
                "amount": "How much are you looking to borrow?",
                "purpose": "What will you use the loan for?",
            }
            field = missing[0]
            return json.dumps(
                {
                    "action": "ask",
                    "missing": missing,
                    "question": question_map[field],
                    "collected": collected,
                }
            )
        return json.dumps(
            {"action": "save", "missing": [], "question": None, "collected": collected}
        )
