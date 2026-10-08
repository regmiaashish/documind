import json
from collections.abc import AsyncIterator

import httpx

from documind.core.budget import GenerationBudget
from documind.core.config import settings
from documind.exceptions import AppError


class GeminiLLM:
    def __init__(self, client: httpx.AsyncClient, api_key: str):
        self.client = client
        self.api_key = api_key

    def _payload(self, system: str, prompt: str, model: str, json_output: bool = False) -> dict:
        config = {"temperature": 0.1, "maxOutputTokens": settings.llm_max_output_tokens}
        if model.startswith("gemini-3"):
            config["thinkingConfig"] = {
                "thinkingLevel": "minimal" if model == "gemini-3.5-flash-lite" else "low"
            }
        if json_output:
            config["responseMimeType"] = "application/json"
        return {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": config,
        }

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise AppError(503, "missing_api_key", "Add GEMINI_API_KEY to .env and run make up.")
        return {"x-goog-api-key": self.api_key}

    @staticmethod
    def _text(data: dict) -> str:
        candidates = data.get("candidates", [])
        if not candidates:
            return ""
        candidate = candidates[0]
        if candidate.get("finishReason") not in (None, "STOP"):
            raise AppError(
                502, "generation_incomplete", "The model could not finish. Try a shorter question."
            )
        return "".join(
            part.get("text", "")
            for part in candidate.get("content", {}).get("parts", [])
            if not part.get("thought")
        )

    async def generate(
        self, system: str, prompt: str, budget: GenerationBudget | None = None
    ) -> str:
        for model in dict.fromkeys([settings.llm_primary_model, settings.llm_fallback_model]):
            if budget is not None:
                budget.reserve(system, prompt, settings.llm_max_output_tokens)
            try:
                response = await self.client.post(
                    f"{settings.gemini_base_url}/models/{model}:generateContent",
                    headers=self._headers(),
                    json=self._payload(system, prompt, model, json_output=True),
                    timeout=30,
                )
                if not response.is_success:
                    continue
                answer = self._text(response.json())
                if answer:
                    return answer
            except (
                httpx.TransportError,
                ValueError,
                KeyError,
                TypeError,
                AttributeError,
                AppError,
            ) as error:
                if isinstance(error, AppError) and error.code == "missing_api_key":
                    raise
        raise AppError(503, "generation_unavailable", "Gemini is unavailable. Please retry.")

    async def stream(
        self, system: str, prompt: str, budget: GenerationBudget | None = None
    ) -> AsyncIterator[tuple[str, str]]:
        """doc-mind-ai: stream native provider tokens; fallback only before the first token."""
        for model in dict.fromkeys([settings.llm_primary_model, settings.llm_fallback_model]):
            if budget is not None:
                budget.reserve(system, prompt, settings.llm_max_output_tokens)
            emitted = False
            completed = False
            try:
                async with self.client.stream(
                    "POST",
                    f"{settings.gemini_base_url}/models/{model}:streamGenerateContent",
                    params={"alt": "sse"},
                    headers=self._headers(),
                    json=self._payload(system, prompt, model),
                    timeout=30,
                ) as response:
                    if not response.is_success:
                        continue
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        raw = line[5:].strip()
                        if not raw or raw == "[DONE]":
                            continue
                        data = json.loads(raw)
                        text = self._text(data)
                        completed = completed or any(
                            candidate.get("finishReason") == "STOP"
                            for candidate in data.get("candidates", [])
                        )
                        if text:
                            emitted = True
                            yield text, model
                if emitted and completed:
                    return
                if emitted:
                    raise AppError(
                        503, "stream_interrupted", "The answer was interrupted. Please retry."
                    )
            except (
                httpx.TransportError,
                ValueError,
                KeyError,
                TypeError,
                AttributeError,
                AppError,
            ) as error:
                if isinstance(error, AppError) and error.code == "missing_api_key":
                    raise
                if emitted:
                    raise AppError(
                        503, "stream_interrupted", "The answer was interrupted. Please retry."
                    ) from error
        raise AppError(503, "generation_unavailable", "Gemini is unavailable. Please retry.")
