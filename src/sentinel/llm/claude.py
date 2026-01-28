"""
Claude API provider implementation.

Primary LLM provider using Anthropic's Claude API.
"""

import anthropic
from anthropic import APIConnectionError, APIError, RateLimitError

from sentinel.core.config import get_settings
from sentinel.core.logging import get_logger
from sentinel.llm.base import LLMConfig, LLMProvider, LLMResponse, ProviderType

logger = get_logger("llm.claude")


class ClaudeProvider(LLMProvider):
    """Anthropic Claude API provider."""

    provider_type = ProviderType.CLAUDE

    def __init__(self, api_key: str | None = None):
        settings = get_settings()
        self.api_key = api_key or settings.anthropic_api_key
        self.default_model = settings.default_model
        self._client: anthropic.AsyncAnthropic | None = None

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def complete(
        self,
        messages: list[dict[str, str]],
        config: LLMConfig,
        task=None,
    ) -> LLMResponse:
        """Generate completion using Claude API."""
        model = config.model or self.default_model

        # Extract system prompt from config or messages
        system_prompt = config.system_prompt
        api_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                api_messages.append(msg)

        # Log request details in debug mode
        logger.debug(f"Claude request: model={model}, max_tokens={config.max_tokens}")
        if system_prompt:
            logger.debug(f"Claude system prompt ({len(system_prompt)} chars)")
        for msg in api_messages:
            preview = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
            logger.debug(f"Claude [{msg['role']}]: {preview}")

        try:
            response = await self.client.messages.create(
                model=model,
                max_tokens=config.max_tokens,
                system=system_prompt or "",
                messages=api_messages,
            )

            content = response.content[0].text if response.content else ""
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost = self._calculate_cost(model, input_tokens, output_tokens)

            logger.debug(f"Claude response ({output_tokens} tokens): {content[:200]}...")
            logger.debug(f"Claude usage: {input_tokens} in, {output_tokens} out, ${cost:.4f}")

            return LLMResponse(
                content=content,
                model=model,
                provider=self.provider_type,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
            )

        except RateLimitError as e:
            logger.warning(f"Rate limited: {e}")
            raise
        except APIConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise
        except APIError as e:
            logger.error(f"API error: {e}")
            raise

    async def health_check(self) -> bool:
        """Check if Claude API is accessible."""
        try:
            # Minimal request to verify connectivity
            response = await self.client.messages.create(
                model=self.default_model,
                max_tokens=10,
                messages=[{"role": "user", "content": "hi"}],
            )
            return bool(response.content)
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
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
