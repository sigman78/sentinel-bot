"""LiteLLM adapter - unified interface for all LLM providers."""

import json
import os
from pathlib import Path
from typing import Any

import litellm
import yaml
from litellm import acompletion

from sentinel.core.logging import get_logger
from sentinel.llm.base import LLMConfig, LLMResponse

logger = get_logger("llm.litellm_adapter")

# Disable LiteLLM's verbose logging
litellm.suppress_debug_info = True
litellm.set_verbose = False


class ModelConfig:
    """Model configuration from YAML."""

    def __init__(self, data: dict[str, Any]):
        self.model_id = data["model_id"]
        self.litellm_name = data["litellm_name"]
        self.provider = data["provider"]
        self.difficulty = data["difficulty"]
        self.cost_per_1m_input = data["cost_per_1m_input"]
        self.cost_per_1m_output = data["cost_per_1m_output"]
        self.max_context = data["max_context"]
        self.avg_latency_ms = data["avg_latency_ms"]
        self.quality_score = data["quality_score"]
        self.multimodal = data.get("multimodal", False)
        self.supports_tools = data.get("supports_tools", True)
        self.notes = data.get("notes", "")
        self.auth_env = data.get("auth_env")
        self.base_url_env = data.get("base_url_env")

    @property
    def api_key(self) -> str | None:
        """Get API key from environment."""
        if not self.auth_env:
            return None
        return os.getenv(self.auth_env)

    @property
    def base_url(self) -> str | None:
        """Get base URL from environment."""
        if not self.base_url_env:
            return None
        return os.getenv(self.base_url_env)

    @property
    def is_available(self) -> bool:
        """Check if model is available (has required credentials)."""
        if self.auth_env and not self.api_key:
            return False
        if self.base_url_env and not self.base_url:
            return False
        return True


class ModelRegistry:
    """Load and manage model configurations from YAML."""

    def __init__(self, config_path: Path | str):
        with open(config_path) as f:
            data = yaml.safe_load(f)

        self.models = {m["model_id"]: ModelConfig(m) for m in data["models"]}
        self.routing_config = data.get("routing", {})

        # Log loaded models
        logger.info(f"Loaded {len(self.models)} models from registry")
        available = [m.model_id for m in self.models.values() if m.is_available]
        logger.info(f"Available models: {', '.join(available)}")

    def get(self, model_id: str) -> ModelConfig | None:
        """Get model config by ID."""
        return self.models.get(model_id)

    def get_by_difficulty(self, difficulty: int) -> list[ModelConfig]:
        """Get all available models matching difficulty level."""
        return [
            m
            for m in self.models.values()
            if m.difficulty == difficulty and m.is_available
        ]

    def rank_by_cost(self, models: list[ModelConfig]) -> list[ModelConfig]:
        """Sort models by total cost (input + output), cheapest first."""
        return sorted(models, key=lambda m: m.cost_per_1m_input + m.cost_per_1m_output)


class LiteLLMAdapter:
    """Adapter for LiteLLM with unified interface."""

    def __init__(self, registry: ModelRegistry):
        self.registry = registry

    def _convert_to_openai_format(self, messages: list[dict]) -> list[dict]:
        """Convert messages to OpenAI format, handling Claude-style image blocks.

        Claude format:
        {"type": "image", "source": {"type": "base64", "data": "...", "media_type": "..."}}

        OpenAI format:
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
        """
        converted = []
        for msg in messages:
            content = msg["content"]

            # String content - pass through
            if isinstance(content, str):
                converted.append(msg)
                continue

            # List content - may have image blocks
            if isinstance(content, list):
                new_content = []
                for block in content:
                    if block.get("type") == "text":
                        # Text block - pass through
                        new_content.append(block)
                    elif block.get("type") == "image":
                        # Claude-style image - convert to OpenAI format
                        source = block.get("source", {})
                        if source.get("type") == "base64":
                            media_type = source.get("media_type", "image/jpeg")
                            data = source.get("data", "")
                            # Create data URL
                            data_url = f"data:{media_type};base64,{data}"
                            new_content.append({
                                "type": "image_url",
                                "image_url": {"url": data_url}
                            })
                    elif block.get("type") == "image_url":
                        # Already OpenAI format - pass through
                        new_content.append(block)

                converted.append({
                    "role": msg["role"],
                    "content": new_content
                })
            else:
                # Unknown format - pass through
                converted.append(msg)

        return converted

    async def complete(
        self,
        model_id: str,
        messages: list[dict],
        config: LLMConfig,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Call LiteLLM completion with model from registry.

        Args:
            model_id: Model ID from registry (e.g., 'claude-sonnet-4')
            messages: OpenAI-format messages
            config: LLM configuration
            tools: Optional tool definitions

        Returns:
            LLMResponse with standardized format
        """
        model_config = self.registry.get(model_id)
        if not model_config:
            raise ValueError(f"Model {model_id} not in registry")

        if not model_config.is_available:
            raise ValueError(
                f"Model {model_id} not available (missing credentials/config)"
            )

        # Convert any Claude-style image blocks to OpenAI format
        messages = self._convert_to_openai_format(messages)

        # Build LiteLLM params
        params = {
            "model": model_config.litellm_name,
            "messages": messages,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
        }

        # Add API key if needed
        if model_config.api_key:
            params["api_key"] = model_config.api_key

        # Add base URL for local models
        if model_config.base_url:
            params["api_base"] = model_config.base_url

        # Add tools if provided
        if tools and model_config.supports_tools:
            params["tools"] = tools

        logger.debug(
            f"LiteLLM request: model={model_config.litellm_name}, "
            f"messages={len(messages)}, tools={len(tools) if tools else 0}"
        )

        try:
            # Call LiteLLM
            response = await acompletion(**params)

            # Extract response
            message = response.choices[0].message
            content = message.content or ""

            # Extract tool calls if present
            tool_calls = None
            if hasattr(message, "tool_calls") and message.tool_calls:
                tool_calls = []
                for tc in message.tool_calls:
                    try:
                        # Parse arguments (may be string or dict)
                        args = tc.function.arguments
                        if isinstance(args, str):
                            args = json.loads(args)

                        tool_calls.append(
                            {
                                "id": tc.id,
                                "name": tc.function.name,
                                "input": args,
                            }
                        )
                    except Exception as e:
                        logger.warning(f"Failed to parse tool call: {e}")
                        continue

            # Get usage stats
            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0

            # Calculate cost from registry
            cost_usd = (
                (input_tokens / 1_000_000) * model_config.cost_per_1m_input
                + (output_tokens / 1_000_000) * model_config.cost_per_1m_output
            )

            logger.debug(
                f"LiteLLM response: model={response.model}, "
                f"tokens={input_tokens}+{output_tokens}, "
                f"cost=${cost_usd:.4f}"
            )

            return LLMResponse(
                content=content,
                model=response.model,
                provider=model_config.provider,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                tool_calls=tool_calls,
            )

        except Exception as e:
            logger.error(f"LiteLLM error for {model_id}: {e}")
            raise


def create_adapter() -> LiteLLMAdapter:
    """Create LiteLLM adapter with model registry."""
    # Find models.yaml relative to this file
    config_path = Path(__file__).parent.parent / "configs" / "models.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Model registry not found at {config_path}")

    registry = ModelRegistry(config_path)
    return LiteLLMAdapter(registry)
