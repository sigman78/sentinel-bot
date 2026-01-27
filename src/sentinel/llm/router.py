"""LLM provider router - selects provider based on task and availability."""

from enum import Enum

from sentinel.core.config import get_settings
from sentinel.core.logging import get_logger
from sentinel.llm.base import LLMConfig, LLMProvider, LLMResponse, ProviderType

logger = get_logger("llm.router")


class TaskType(Enum):
    """Task categories for model selection."""
    CHAT = "chat"              # General conversation - use primary
    REASONING = "reasoning"    # Complex reasoning - use best available
    SIMPLE = "simple"          # Simple tasks - use cheap/fast model
    BACKGROUND = "background"  # Async tasks - use local if available


# Model recommendations per task type
TASK_MODELS = {
    TaskType.CHAT: {"provider": ProviderType.CLAUDE, "model": None},  # Use default
    TaskType.REASONING: {"provider": ProviderType.CLAUDE, "model": "claude-opus-4-20250514"},
    TaskType.SIMPLE: {"provider": ProviderType.OPENROUTER, "model": "openai/gpt-4o-mini"},
    TaskType.BACKGROUND: {"provider": ProviderType.LOCAL, "model": None},
}


class LLMRouter:
    """Routes LLM requests to appropriate provider with fallback."""

    def __init__(self):
        self._providers: dict[ProviderType, LLMProvider] = {}
        self._fallback_order = [
            ProviderType.CLAUDE,
            ProviderType.OPENROUTER,
            ProviderType.LOCAL,
        ]

    def register(self, provider: LLMProvider) -> None:
        """Register a provider."""
        self._providers[provider.provider_type] = provider
        logger.info(f"Registered provider: {provider.provider_type.value}")

    def get(self, provider_type: ProviderType) -> LLMProvider | None:
        """Get specific provider."""
        return self._providers.get(provider_type)

    @property
    def available_providers(self) -> list[ProviderType]:
        """List registered providers."""
        return list(self._providers.keys())

    async def complete(
        self,
        messages: list[dict[str, str]],
        config: LLMConfig,
        preferred: ProviderType | None = None,
        task: TaskType | None = None,
    ) -> LLMResponse:
        """Route completion to best available provider."""
        # Determine provider order based on task or preference
        if task and not preferred:
            rec = TASK_MODELS.get(task, {})
            preferred = rec.get("provider")
            if not config.model:
                config = LLMConfig(
                    model=rec.get("model"),
                    max_tokens=config.max_tokens,
                    temperature=config.temperature,
                    system_prompt=config.system_prompt,
                )

        # Build provider order
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

    async def complete_simple(self, prompt: str, task: TaskType = TaskType.SIMPLE) -> str:
        """Convenience method for simple single-turn completions."""
        messages = [{"role": "user", "content": prompt}]
        config = LLMConfig(model=None, max_tokens=1024, temperature=0.7)
        response = await self.complete(messages, config, task=task)
        return response.content

    async def health_check_all(self) -> dict[ProviderType, bool]:
        """Check health of all registered providers."""
        results = {}
        for ptype, provider in self._providers.items():
            results[ptype] = await provider.health_check()
        return results

    async def close_all(self) -> None:
        """Close all provider connections."""
        for provider in self._providers.values():
            if hasattr(provider, "close"):
                await provider.close()


def create_default_router() -> LLMRouter:
    """Create router with providers from settings."""
    from sentinel.llm.claude import ClaudeProvider
    from sentinel.llm.local import LocalProvider
    from sentinel.llm.openrouter import OpenRouterProvider

    settings = get_settings()
    router = LLMRouter()

    # Claude (primary)
    if settings.anthropic_api_key:
        try:
            router.register(ClaudeProvider())
        except Exception as e:
            logger.warning(f"Failed to init Claude: {e}")

    # OpenRouter (fallback)
    if settings.openrouter_api_key:
        try:
            router.register(OpenRouterProvider())
        except Exception as e:
            logger.warning(f"Failed to init OpenRouter: {e}")

    # Local LLM (background tasks)
    if settings.local_llm_url:
        try:
            local = LocalProvider()
            router.register(local)
        except Exception as e:
            logger.warning(f"Failed to init local LLM: {e}")

    return router
