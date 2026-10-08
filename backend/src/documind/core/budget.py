"""Conservative reservations bound agent provider attempts, including failed attempts."""

from dataclasses import dataclass

from documind.core.config import settings
from documind.exceptions import AppError


@dataclass
class GenerationBudget:
    reserved_tokens: int = 0
    reserved_usd: float = 0

    def reserve(self, system: str, prompt: str, output_tokens: int) -> None:
        # UTF-8 bytes deliberately overestimate input tokens for the configured Gemini models.
        tokens = len(system.encode()) + len(prompt.encode()) + output_tokens + 256
        cost = tokens * settings.agent_token_price_ceiling_usd / 1_000_000
        if (
            self.reserved_tokens + tokens > settings.agent_max_tokens
            or self.reserved_usd + cost > settings.agent_max_cost_usd
        ):
            raise AppError(
                429,
                "agent_budget_exceeded",
                "This request exceeded the tool budget. Try one shorter request.",
            )
        self.reserved_tokens += tokens
        self.reserved_usd += cost
