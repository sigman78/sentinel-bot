"""Local LLM provider - OpenAI-compatible API for Ollama, LM Studio, etc."""

import httpx

from sentinel.core.config import get_settings
from sentinel.core.logging import get_logger
from sentinel.llm.base import LLMConfig, LLMProvider, LLMResponse, ProviderType

logger = get_logger("llm.local")


class LocalProvider(LLMProvider):
    """Local LLM via OpenAI-compatible API (Ollama, LM Studio, vLLM, etc.)."""

    provider_type = ProviderType.LOCAL

    def __init__(self, base_url: str | None = None):
        settings = get_settings()
        self.base_url = base_url or settings.local_llm_url
        self.default_model = "local"  # Model name varies by backend
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=300.0,  # Local models can be slow
            )
        return self._client

    async def complete(
        self,
        messages: list[dict],
        config: LLMConfig,
        task=None,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Generate completion via local OpenAI-compatible API.

        Supports both text-only and multimodal (vision) messages.
        Vision support depends on the local model (LLaVA, Llama 3.2 Vision, etc.)
        """
        model = config.model or self.default_model

        # Convert messages to OpenAI format (may have Claude-style image blocks)
        openai_messages = self._convert_to_openai_format(messages)

        payload = {
            "model": model,
            "messages": openai_messages,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "stream": False,
        }

        # Add tools if provided (OpenAI function calling format)
        if tools:
            payload["tools"] = tools

        # Log request details in debug mode
        logger.debug(f"Local request: model={model}, url={self.base_url}")
        if tools:
            logger.debug(f"Local tools: {len(tools)} available")
        for msg in openai_messages:
            content = msg["content"]
            # Handle both text strings and content blocks (vision)
            if isinstance(content, str):
                preview = content[:100] + "..." if len(content) > 100 else content
                logger.debug(f"Local [{msg['role']}]: {preview}")
            elif isinstance(content, list):
                # Multimodal content (text + images)
                text_parts = [b.get("text", "") for b in content if b.get("type") == "text"]
                image_count = sum(1 for b in content if b.get("type") == "image_url")
                preview = " ".join(text_parts)[:100]
                if image_count:
                    logger.debug(f"Local [{msg['role']}]: [+{image_count} image(s)] {preview}")
                else:
                    logger.debug(f"Local [{msg['role']}]: {preview}")

        try:
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()

            message = data["choices"][0]["message"]
            content = message.get("content") or ""
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

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

            logger.debug(f"Local response ({output_tokens} tokens): {content[:200] if content else '[tool calls]'}...")
            if tool_calls:
                logger.debug(f"Local tool calls: {[tc['name'] for tc in tool_calls]}")
            logger.debug(f"Local usage: {input_tokens} in, {output_tokens} out")

            return LLMResponse(
                content=content,
                model=data.get("model", model),
                provider=self.provider_type,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=0.0,
                tool_calls=tool_calls,
            )

        except httpx.ConnectError as e:
            logger.warning(f"Local LLM not reachable at {self.base_url}: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"Local LLM error: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Local LLM error: {e}")
            raise

    async def health_check(self) -> bool:
        """Check if local LLM server is running."""
        try:
            # Try /models endpoint (OpenAI-compatible)
            response = await self.client.get("/models")
            if response.status_code == 200:
                return True
            # Fallback: try /v1/models
            response = await self.client.get("/v1/models")
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Local LLM health check failed: {e}")
            return False

    async def list_models(self) -> list[str]:
        """List available models from local server."""
        try:
            response = await self.client.get("/models")
            if response.status_code == 200:
                data = response.json()
                return [m.get("id", m.get("name", "unknown")) for m in data.get("data", [])]
        except Exception:
            pass
        return []

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

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
