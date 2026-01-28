"""OpenRouter API provider - access to 400+ models via unified API."""

import httpx

from sentinel.core.config import get_settings
from sentinel.core.logging import get_logger
from sentinel.llm.base import LLMConfig, LLMProvider, LLMResponse, ProviderType

logger = get_logger("llm.openrouter")

OPENROUTER_BASE = "https://openrouter.ai/api/v1"


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
        task=None,
        tools: list[dict] | None = None,
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

        # Add tools if provided (OpenAI function calling format)
        if tools:
            payload["tools"] = tools

        # Log request details in debug mode
        logger.debug(f"OpenRouter request: model={model}, max_tokens={config.max_tokens}")
        if tools:
            logger.debug(f"OpenRouter tools: {len(tools)} available")
        for msg in messages:
            preview = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
            logger.debug(f"OpenRouter [{msg['role']}]: {preview}")

        try:
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()

            message = data["choices"][0]["message"]
            content = message.get("content") or ""
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            cost = self._calculate_cost(model, input_tokens, output_tokens)

            # Extract tool calls if present (OpenAI format)
            tool_calls = None
            if "tool_calls" in message and message["tool_calls"]:
                tool_calls = []
                for tc in message["tool_calls"]:
                    import json
                    tool_calls.append({
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "input": json.loads(tc["function"]["arguments"]),
                    })

            logger.debug(f"OpenRouter response ({output_tokens} tokens): {content[:200] if content else '[tool calls]'}...")
            if tool_calls:
                logger.debug(f"OpenRouter tool calls: {[tc['name'] for tc in tool_calls]}")
            logger.debug(f"OpenRouter usage: {input_tokens}→{output_tokens} tok, ${cost:.4f}")

            return LLMResponse(
                content=content,
                model=model,
                provider=self.provider_type,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                tool_calls=tool_calls,
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
        """Calculate cost in USD using registry."""
        from sentinel.llm.registry import get_model_info

        model_info = get_model_info(model)
        if model_info:
            input_cost = (input_tokens / 1_000_000) * model_info.cost_per_1m_input
            output_cost = (output_tokens / 1_000_000) * model_info.cost_per_1m_output
            return input_cost + output_cost

        # Fallback for unknown models
        logger.warning(f"Unknown model {model}, cost calculation unavailable")
        return 0.0

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
