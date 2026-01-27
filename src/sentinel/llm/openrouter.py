"""OpenRouter API provider - access to 400+ models via unified API."""

import httpx

from sentinel.core.config import get_settings
from sentinel.core.logging import get_logger
from sentinel.llm.base import LLMConfig, LLMProvider, LLMResponse, ProviderType

logger = get_logger("llm.openrouter")

OPENROUTER_BASE = "https://openrouter.ai/api/v1"

# Popular models and their pricing (per 1M tokens)
PRICING = {
    "anthropic/claude-3.5-sonnet": {"input": 3.0, "output": 15.0},
    "anthropic/claude-3-haiku": {"input": 0.25, "output": 1.25},
    "openai/gpt-4o": {"input": 2.5, "output": 10.0},
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "google/gemini-pro-1.5": {"input": 1.25, "output": 5.0},
    "meta-llama/llama-3.1-70b-instruct": {"input": 0.52, "output": 0.75},
    "mistralai/mistral-large": {"input": 2.0, "output": 6.0},
}


class OpenRouterProvider(LLMProvider):
    """OpenRouter multi-model provider."""

    provider_type = ProviderType.OPENROUTER

    def __init__(self, api_key: str | None = None):
        settings = get_settings()
        self.api_key = api_key or settings.openrouter_api_key
        self.default_model = settings.fallback_model
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=OPENROUTER_BASE,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://github.com/sentinel-ai",
                    "X-Title": "Sentinel",
                },
                timeout=120.0,
            )
        return self._client

    async def complete(
        self,
        messages: list[dict[str, str]],
        config: LLMConfig,
    ) -> LLMResponse:
        """Generate completion via OpenRouter."""
        model = config.model or self.default_model

        # OpenRouter uses OpenAI-compatible format
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
        }

        try:
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            cost = self._calculate_cost(model, input_tokens, output_tokens)

            logger.debug(f"OpenRouter [{model}]: {input_tokens}→{output_tokens} tok, ${cost:.4f}")

            return LLMResponse(
                content=content,
                model=model,
                provider=self.provider_type,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                metadata={"openrouter_id": data.get("id")},
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"OpenRouter HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"OpenRouter error: {e}")
            raise

    async def health_check(self) -> bool:
        """Check if OpenRouter is accessible."""
        try:
            response = await self.client.get("/models")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"OpenRouter health check failed: {e}")
            return False

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost in USD."""
        prices = PRICING.get(model, {"input": 1.0, "output": 2.0})  # Default fallback
        input_cost = (input_tokens / 1_000_000) * prices["input"]
        output_cost = (output_tokens / 1_000_000) * prices["output"]
        return input_cost + output_cost

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
