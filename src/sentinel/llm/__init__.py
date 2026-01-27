"""
LLM module - language model provider abstraction.

Providers:
- claude: Anthropic Claude API (primary)
- openrouter: OpenRouter multi-model API (fallback)
- local: Local LLMs via OpenAI-compatible API (async tasks)

Router selects provider based on task requirements and availability.
"""
