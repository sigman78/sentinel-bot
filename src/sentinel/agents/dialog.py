"""Dialog agent - primary user-facing conversation handler."""

from datetime import datetime
from uuid import uuid4

from sentinel.agents.base import AgentConfig, AgentState, BaseAgent
from sentinel.core.logging import get_logger
from sentinel.core.types import AgentType, ContentType, Message
from sentinel.llm.base import LLMConfig, LLMProvider
from sentinel.memory.base import MemoryEntry, MemoryStore, MemoryType

logger = get_logger("agents.dialog")

DEFAULT_SYSTEM_PROMPT = """You are Sentinel, a personal AI assistant.

User: {user_name}
{user_context}

Recent memories:
{memories}

Be direct, remember context, respect privacy."""


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
        self._max_history = 20
        self._user_name = "User"
        self._user_context = ""

    async def initialize(self) -> None:
        """Load user profile from core memory."""
        await super().initialize()
        await self._load_user_profile()

    async def _load_user_profile(self) -> None:
        """Load or bootstrap user profile from core memory."""
        if not hasattr(self.memory, "get_core"):
            return

        name = await self.memory.get_core("user_name")
        if name:
            self._user_name = name
        else:
            await self.memory.set_core("user_name", "User")

        context = await self.memory.get_core("user_context")
        if context:
            self._user_context = context

    async def process(self, message: Message) -> Message:
        """Process user message and generate response."""
        self.state = AgentState.ACTIVE

        self.context.conversation.append(message)
        self._trim_history()

        # Retrieve relevant memories
        memories = await self._get_relevant_memories(message.content)
        memory_text = self._format_memories(memories)

        # Build prompt with user profile and memories
        system_prompt = self.config.system_prompt.format(
            user_name=self._user_name,
            user_context=self._user_context,
            memories=memory_text,
        )

        llm_messages = [{"role": "system", "content": system_prompt}]
        for msg in self.context.conversation:
            llm_messages.append(msg.to_llm_format())

        llm_config = LLMConfig(model=None, max_tokens=2048, temperature=0.7)
        response = await self.llm.complete(llm_messages, llm_config)

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

        self.context.conversation.append(response_msg)

        # Persist exchange to episodic memory
        await self._persist_exchange(message, response_msg)

        self.state = AgentState.READY
        return response_msg

    async def _persist_exchange(self, user_msg: Message, assistant_msg: Message) -> None:
        """Save conversation exchange to episodic memory."""
        try:
            summary = f"User: {user_msg.content[:100]}... → Assistant responded"
            if len(user_msg.content) <= 100:
                summary = f"User: {user_msg.content}"

            entry = MemoryEntry(
                id=str(uuid4()),
                type=MemoryType.EPISODIC,
                content=summary,
                timestamp=datetime.now(),
                importance=0.5,
                metadata={"user_msg_id": user_msg.id, "assistant_msg_id": assistant_msg.id},
            )
            await self.memory.store(entry)
        except Exception as e:
            logger.warning(f"Failed to persist exchange: {e}")

    async def _get_relevant_memories(self, query: str) -> list[dict]:
        """Retrieve memories relevant to current query."""
        try:
            entries = await self.memory.retrieve(query, limit=5)
            if not entries and hasattr(self.memory, "get_recent"):
                entries = await self.memory.get_recent(limit=5)
            return [{"content": e.content, "timestamp": e.timestamp} for e in entries]
        except Exception as e:
            logger.warning(f"Memory retrieval failed: {e}")
            return []

    def _format_memories(self, memories: list[dict]) -> str:
        """Format memories for prompt injection."""
        if not memories:
            return "(No prior context)"
        lines = []
        for m in memories:
            ts = m["timestamp"].strftime("%Y-%m-%d") if m.get("timestamp") else ""
            lines.append(f"- [{ts}] {m['content']}" if ts else f"- {m['content']}")
        return "\n".join(lines)

    def _trim_history(self) -> None:
        """Keep conversation history within limits."""
        if len(self.context.conversation) > self._max_history:
            self.context.conversation = self.context.conversation[-self._max_history:]

    async def update_user_profile(self, key: str, value: str) -> None:
        """Update user profile in core memory."""
        if hasattr(self.memory, "set_core"):
            await self.memory.set_core(key, value)
            if key == "user_name":
                self._user_name = value
            elif key == "user_context":
                self._user_context = value
