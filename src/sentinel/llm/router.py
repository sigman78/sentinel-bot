"""
LLM provider router.

Selects appropriate provider based on task requirements and availability.
Handles fallback logic when primary provider fails.
"""

from sentinel.core.logging import get_logger
from sentinel.llm.base import LLMConfig, LLMProvider, LLMResponse, ProviderType
from sentinel.llm.claude import ClaudeProvider

logger = get_logger("llm.router")


class LLMRouter:
    """Routes LLM requests to appropriate provider with fallback."""

    def __init__(self):
        self._providers: dict[ProviderType, LLMProvider] = {}
        self._fallback_order = [ProviderType.CLAUDE]  # Extend with OpenRouter, Local

    def register(self, provider: LLMProvider) -> None:
        """Register a provider."""
        self._providers[provider.provider_type] = provider
        logger.info(f"Registered provider: {provider.provider_type.value}")

    def get(self, provider_type: ProviderType) -> LLMProvider | None:
        """Get specific provider."""
        return self._providers.get(provider_type)

    async def complete(
        self,
        messages: list[dict[str, str]],
        config: LLMConfig,
        preferred: ProviderType | None = None,
    ) -> LLMResponse:
        """
        Route completion request to best available provider.

        Args:
            messages: Conversation messages
            config: LLM configuration
            preferred: Preferred provider (falls back if unavailable)

        Returns:
            LLMResponse from successful provider

        Raises:
            RuntimeError: If all providers fail
        """
        # Build provider order: preferred first, then fallback order
        order = []
        if preferred and preferred in self._providers:
            order.append(preferred)
        for p in self._fallback_order:
            if p not in order and p in self._providers:
                order.append(p)

        if not order:
            raise RuntimeError("No LLM providers registered")

        last_error: Exception | None = None
        for provider_type in order:
            provider = self._providers[provider_type]
            try:
                response = await provider.complete(messages, config)
                return response
            except Exception as e:
                logger.warning(f"Provider {provider_type.value} failed: {e}")
                last_error = e
                continue

        raise RuntimeError(f"All providers failed. Last error: {last_error}")

    async def health_check_all(self) -> dict[ProviderType, bool]:
        """Check health of all registered providers."""
        results = {}
        for ptype, provider in self._providers.items():
            results[ptype] = await provider.health_check()
        return results


def create_default_router() -> LLMRouter:
    """Create router with default providers from settings."""
    router = LLMRouter()

    # Register Claude as primary
    try:
        claude = ClaudeProvider()
        if claude.api_key:
            router.register(claude)
    except Exception as e:
        logger.warning(f"Failed to initialize Claude provider: {e}")

    # TODO: Add OpenRouter and Local providers

    return router
