"""
Main dialog agent.

Primary user-facing agent handling conversations.
Uses Claude as LLM with memory-augmented context.
"""

from datetime import datetime
from uuid import uuid4

from sentinel.agents.base import AgentConfig, AgentState, BaseAgent
from sentinel.core.logging import get_logger
from sentinel.core.types import AgentType, ContentType, Message
from sentinel.llm.base import LLMConfig, LLMProvider
from sentinel.memory.base import MemoryStore

logger = get_logger("agents.dialog")

DEFAULT_SYSTEM_PROMPT = """You are Sentinel, a personal AI assistant.

You have access to memories about the user and past conversations.
Be helpful, concise, and remember context from previous interactions.

Current memories:
{memories}

Guidelines:
- Be direct and helpful
- Remember user preferences and past context
- Ask for clarification when needed
- Respect user privacy
"""


class DialogAgent(BaseAgent):
    """Main conversation agent."""

    def __init__(
        self,
        llm: LLMProvider,
        memory: MemoryStore,
        system_prompt: str | None = None,
    ):
        config = AgentConfig(
            agent_type=AgentType.DIALOG,
            system_prompt=system_prompt or DEFAULT_SYSTEM_PROMPT,
        )
        super().__init__(config, llm, memory)
        self._max_history = 20  # Keep last N messages in context

    async def initialize(self) -> None:
        """Load relevant memories for context."""
        await super().initialize()
        # Memory retrieval happens per-message to get fresh context

    async def process(self, message: Message) -> Message:
        """Process user message and generate response."""
        self.state = AgentState.ACTIVE

        # Add user message to conversation
        self.context.conversation.append(message)
        self._trim_history()

        # Retrieve relevant memories
        memories = await self._get_relevant_memories(message.content)
        memory_text = self._format_memories(memories)

        # Build prompt with memories
        system_prompt = self.config.system_prompt.format(memories=memory_text)

        # Build messages for LLM
        llm_messages = [{"role": "system", "content": system_prompt}]
        for msg in self.context.conversation:
            llm_messages.append(msg.to_llm_format())

        # Generate response
        llm_config = LLMConfig(model=None, max_tokens=2048, temperature=0.7)
        response = await self.llm.complete(llm_messages, llm_config)

        # Create response message
        response_msg = Message(
            id=str(uuid4()),
            timestamp=datetime.now(),
            role="assistant",
            content=response.content,
            content_type=ContentType.TEXT,
            metadata={
                "model": response.model,
                "tokens": response.input_tokens + response.output_tokens,
                "cost_usd": response.cost_usd,
            },
        )

        # Add to conversation
        self.context.conversation.append(response_msg)

        self.state = AgentState.READY
        return response_msg

    async def _get_relevant_memories(self, query: str) -> list[dict]:
        """Retrieve memories relevant to current query."""
        try:
            entries = await self.memory.retrieve(query, limit=5)
            return [{"content": e.content, "timestamp": e.timestamp} for e in entries]
        except Exception as e:
            logger.warning(f"Memory retrieval failed: {e}")
            return []

    def _format_memories(self, memories: list[dict]) -> str:
        """Format memories for prompt injection."""
        if not memories:
            return "(No relevant memories)"
        lines = []
        for m in memories:
            ts = m["timestamp"].strftime("%Y-%m-%d") if m.get("timestamp") else "unknown"
            lines.append(f"- [{ts}] {m['content']}")
        return "\n".join(lines)

    def _trim_history(self) -> None:
        """Keep conversation history within limits."""
        if len(self.context.conversation) > self._max_history:
            # Keep system context awareness by preserving first and recent messages
            self.context.conversation = self.context.conversation[-self._max_history:]
