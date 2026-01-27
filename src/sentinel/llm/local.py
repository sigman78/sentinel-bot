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
        messages: list[dict[str, str]],
        config: LLMConfig,
    ) -> LLMResponse:
        """Generate completion via local OpenAI-compatible API."""
        model = config.model or self.default_model

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "stream": False,
        }

        try:
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            # Local models have no API cost
            logger.debug(f"Local [{model}]: {input_tokens} in, {output_tokens} out")

            return LLMResponse(
                content=content,
                model=data.get("model", model),
                provider=self.provider_type,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=0.0,
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

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
