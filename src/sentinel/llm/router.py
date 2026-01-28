"""LLM provider router - selects provider based on task and availability."""

from enum import Enum

from sentinel.core.config import get_settings
from sentinel.core.logging import get_logger
from sentinel.llm.base import LLMConfig, LLMProvider, LLMResponse, ProviderType

logger = get_logger("llm.router")


class TaskType(Enum):
    """Task categories for model selection."""
    CHAT = "chat"
    REASONING = "reasoning"
    SIMPLE = "simple"
    BACKGROUND = "background"
    SUMMARIZATION = "summarization"
    TOOL_CALL = "tool_call"
    INTER_AGENT = "inter_agent"
    FACT_EXTRACTION = "fact_extraction"
    IMPORTANCE_SCORING = "importance_scoring"


# Map task types to difficulty levels (1=Easy, 2=Intermediate, 3=Hard)
TASK_DIFFICULTY: dict[TaskType, int] = {
    TaskType.CHAT: 3,  # Hard - complex conversation, maintain personality
    TaskType.REASONING: 3,  # Hard - complex logic
    TaskType.FACT_EXTRACTION: 2,  # Intermediate - extract structured info
    TaskType.SUMMARIZATION: 2,  # Intermediate - condense content
    TaskType.BACKGROUND: 2,  # Intermediate - consolidation tasks
    TaskType.SIMPLE: 1,  # Easy - basic operations
    TaskType.TOOL_CALL: 1,  # Easy - structured I/O
    TaskType.INTER_AGENT: 1,  # Easy - high volume simple comms
    TaskType.IMPORTANCE_SCORING: 1,  # Easy - simple classification
}


class LLMRouter:
    """Routes LLM requests to appropriate provider with fallback."""

    def __init__(self):
        self._providers: dict[ProviderType, LLMProvider] = {}
        self._cost_tracker: "CostTracker | None" = None

    def set_cost_tracker(self, tracker: "CostTracker") -> None:
        """Set cost tracking service."""
        self._cost_tracker = tracker

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
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Route completion to optimal provider based on task/cost.

        Args:
            messages: List of message dicts with role/content
            config: LLM configuration (model, tokens, temperature)
            preferred: Preferred provider (optional)
            task: Task type for intelligent routing (optional)

        Returns:
            LLMResponse with content and metadata
        """
        from sentinel.llm.registry import MODEL_REGISTRY, get_models_by_difficulty, rank_models_by_cost

        # 1. Determine difficulty level from task
        difficulty = TASK_DIFFICULTY.get(task, 2) if task else 2

        # 2. Check budget - downgrade if approaching limit
        if self._cost_tracker and self._cost_tracker.should_use_cheaper_model():
            if difficulty > 1:
                original_difficulty = difficulty
                difficulty = max(1, difficulty - 1)
                logger.info(
                    f"Budget at {self._cost_tracker.get_cost_summary()['percent_used']:.1f}%: "
                    f"downgraded difficulty {original_difficulty} -> {difficulty}"
                )

        # 3. Get candidate models for this difficulty
        candidates = get_models_by_difficulty(difficulty)

        # 4. Filter by available providers
        available = [m for m in candidates if m.provider in self._providers]

        if not available:
            # Fallback: try easier difficulty if none available
            if difficulty > 1:
                logger.warning(
                    f"No models available for difficulty {difficulty}, trying easier"
                )
                return await self.complete(
                    messages, config, preferred=None, task=TaskType.SIMPLE, tools=tools
                )

            # If even easy models are unavailable, use cheapest available model
            fallback = [m for m in MODEL_REGISTRY.values() if m.provider in self._providers]
            if not fallback:
                raise RuntimeError("No providers registered")

            logger.warning(
                "No models available for difficulty 1; falling back to cheapest available"
            )
            available = rank_models_by_cost(fallback)

        # 5. Honor preferred provider if specified
        if preferred:
            available = [m for m in available if m.provider == preferred] + [
                m for m in available if m.provider != preferred
            ]

        # 6. Sort by cost (cheapest first within difficulty)
        available = rank_models_by_cost(available)

        # 7. Try each candidate in order
        last_error: Exception | None = None
        for model_cap in available:
            provider = self._providers[model_cap.provider]

            # Use explicit model from config if set, otherwise from registry
            model_to_use = config.model or model_cap.model_id

            try:
                response = await provider.complete(
                    messages,
                    LLMConfig(
                        model=model_to_use,
                        max_tokens=config.max_tokens,
                        temperature=config.temperature,
                        system_prompt=config.system_prompt,
                    ),
                    task=task,
                    tools=tools,
                )

                # Track cost
                if self._cost_tracker:
                    self._cost_tracker.add_cost(response.cost_usd)

                logger.info(
                    f"Task {task.value if task else 'default'}: "
                    f"used {response.model} (difficulty={difficulty}, "
                    f"cost=${response.cost_usd:.4f})"
                )
                return response

            except Exception as e:
                logger.warning(
                    f"Model {model_to_use} ({model_cap.provider.value}) failed: {e}"
                )
                last_error = e
                continue

        # 8. If all same-difficulty failed, try easier models as fallback
        if difficulty > 1:
            logger.warning("All models failed, trying easier difficulty")
            return await self.complete(
                messages, config, preferred=None, task=TaskType.SIMPLE, tools=tools
            )

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
    from sentinel.llm.cost_tracker import CostTracker
    from sentinel.llm.local import LocalProvider
    from sentinel.llm.openrouter import OpenRouterProvider

    settings = get_settings()
    router = LLMRouter()

    # Set up cost tracking
    cost_tracker = CostTracker(daily_limit=settings.daily_cost_limit)
    router.set_cost_tracker(cost_tracker)

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
