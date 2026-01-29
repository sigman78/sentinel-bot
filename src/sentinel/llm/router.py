"""LLM provider router - task-aware model selection with LiteLLM."""

from enum import Enum

from sentinel.core.logging import get_logger
from sentinel.llm.base import LLMConfig, LLMResponse
from sentinel.llm.litellm_adapter import LiteLLMAdapter, create_adapter

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


class SentinelLLMRouter:
    """Router with task-aware model selection using LiteLLM."""

    def __init__(self, adapter: LiteLLMAdapter):
        self.adapter = adapter
        self.registry = adapter.registry
        self._cost_tracker = None

        # Load task difficulty from config
        routing = self.registry.routing_config
        self.task_difficulty = routing.get("task_difficulty", {})
        self.budget_threshold = routing.get("budget_threshold", 0.8)

        logger.info(
            f"Router initialized with {len(self.registry.models)} models, "
            f"budget_threshold={self.budget_threshold}"
        )

    def set_cost_tracker(self, tracker) -> None:
        """Set cost tracking service."""
        self._cost_tracker = tracker

    @property
    def available_providers(self) -> list[str]:
        """Get list of available providers (backward compatibility).

        Returns non-empty list if any models are configured and available.
        """
        available = [m.provider for m in self.registry.models.values() if m.is_available]
        return list(set(available))  # Unique providers

    async def complete(
        self,
        messages: list[dict],
        config: LLMConfig,
        preferred: str | None = None,
        task: TaskType | None = None,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Route completion to optimal model based on task/cost.

        Args:
            messages: List of message dicts with role/content
            config: LLM configuration (model, tokens, temperature)
            preferred: Preferred model ID (optional)
            task: Task type for intelligent routing (optional)
            tools: Tool definitions for function calling (optional)

        Returns:
            LLMResponse with content and metadata
        """
        # 1. Determine difficulty from task
        difficulty = self.task_difficulty.get(task.value if task else "simple", 2)

        # 2. Check budget - downgrade if approaching limit
        if self._cost_tracker and self._cost_tracker.should_use_cheaper_model():
            if difficulty > 1:
                original = difficulty
                difficulty = max(1, difficulty - 1)
                summary = self._cost_tracker.get_cost_summary()
                logger.info(
                    f"Budget at {summary['percent_used']:.1f}%: "
                    f"downgraded difficulty {original} -> {difficulty}"
                )

        # 3. Get candidate models for this difficulty
        candidates = self.registry.get_by_difficulty(difficulty)

        if not candidates:
            # Fallback to easier difficulty
            if difficulty > 1:
                logger.warning(f"No models for difficulty {difficulty}, trying easier")
                return await self.complete(
                    messages, config, preferred=None, task=TaskType.SIMPLE, tools=tools
                )
            raise RuntimeError("No models available in registry")

        # 4. Honor preferred model if specified and available
        if preferred:
            pref_model = self.registry.get(preferred)
            if pref_model and pref_model.is_available:
                # Put preferred model first
                candidates = [
                    m for m in candidates if m.model_id == preferred
                ] + [m for m in candidates if m.model_id != preferred]

        # 5. Sort by cost (cheapest first within difficulty)
        candidates = self.registry.rank_by_cost(candidates)

        # 6. Try each candidate in order
        last_error: Exception | None = None
        for model_config in candidates:
            try:
                # Use explicit model from config if set, otherwise from routing
                model_to_use = config.model or model_config.model_id

                response = await self.adapter.complete(
                    model_id=model_to_use,
                    messages=messages,
                    config=config,
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
                logger.warning(f"Model {model_config.model_id} failed: {e}")
                last_error = e
                continue

        # 7. All same-difficulty failed - try easier models as fallback
        if difficulty > 1:
            logger.warning("All models failed, trying easier difficulty")
            return await self.complete(
                messages, config, preferred=None, task=TaskType.SIMPLE, tools=tools
            )

        raise RuntimeError(f"All models failed. Last error: {last_error}")

    async def complete_simple(self, prompt: str, task: TaskType = TaskType.SIMPLE) -> str:
        """Convenience method for simple single-turn completions."""
        messages = [{"role": "user", "content": prompt}]
        config = LLMConfig(model=None, max_tokens=1024, temperature=0.7)
        response = await self.complete(messages, config, task=task)
        return response.content


def create_default_router() -> SentinelLLMRouter:
    """Create router with LiteLLM adapter and cost tracking."""
    from sentinel.core.config import get_settings
    from sentinel.llm.cost_tracker import CostTracker

    settings = get_settings()

    adapter = create_adapter()
    router = SentinelLLMRouter(adapter)

    # Set up cost tracking
    cost_tracker = CostTracker(daily_limit=settings.daily_cost_limit)
    router.set_cost_tracker(cost_tracker)

    return router
