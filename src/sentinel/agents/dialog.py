"""Dialog agent - primary user-facing conversation handler with persona."""

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sentinel.agents.base import AgentConfig, AgentState, BaseAgent
from sentinel.core.config import get_settings
from sentinel.core.logging import get_logger
from sentinel.core.types import AgentType, ContentType, Message
from sentinel.llm.base import LLMConfig, LLMProvider
from sentinel.llm.router import TaskType
from sentinel.memory.base import MemoryEntry, MemoryStore, MemoryType
from sentinel.tools.executor import ToolExecutor
from sentinel.tools.parser import ToolCall
from sentinel.tools.registry import ToolRegistry

SUMMARIZE_PROMPT = """Summarize this conversation in 2-3 sentences, focusing on:
- Key topics discussed
- Decisions made or tasks completed
- Important information shared

Conversation:
{conversation}

Summary:"""

IMPORTANCE_PROMPT = """Rate the importance of this conversation on a scale of 0.0-1.0.
Consider: actionable items, personal details learned, decisions made, emotional significance.
Return ONLY a number like 0.7

Conversation summary: {summary}

Rating:"""

logger = get_logger("agents.dialog")

FALLBACK_IDENTITY = """I'm Sentinel, your personal AI assistant.
I help with tasks, remember context, and work efficiently."""

SYSTEM_TEMPLATE = """{identity}

## Current Context
User: {user_name}
{user_context}

## Agenda
{agenda}

## Recent Memories
{memories}

{tools}
"""


class DialogAgent(BaseAgent):
    """Main conversation agent with persona from identity.md."""

    def __init__(
        self,
        llm: LLMProvider,
        memory: MemoryStore,
        identity_path: Path | None = None,
        agenda_path: Path | None = None,
        tool_registry: ToolRegistry | None = None,
    ):
        config = AgentConfig(
            agent_type=AgentType.DIALOG,
            system_prompt=SYSTEM_TEMPLATE,
        )
        super().__init__(config, llm, memory)

        settings = get_settings()
        self._identity_path = identity_path or settings.identity_path
        self._agenda_path = agenda_path or settings.agenda_path

        self._max_history = 20
        self._user_name = "User"
        self._user_context = ""
        self._identity = FALLBACK_IDENTITY
        self._agenda = ""

        # Tool calling support
        self._tool_registry = tool_registry
        self._tool_executor = ToolExecutor(tool_registry) if tool_registry else None

    async def initialize(self) -> None:
        """Load identity, agenda, and user profile."""
        await super().initialize()
        self._load_identity()
        self._load_agenda()
        await self._load_user_profile()

    def _load_identity(self) -> None:
        """Load agent identity/persona from file."""
        try:
            if self._identity_path.exists():
                self._identity = self._identity_path.read_text(encoding="utf-8")
                logger.info(f"Loaded identity from {self._identity_path}")
        except Exception as e:
            logger.warning(f"Failed to load identity: {e}")

    def _load_agenda(self) -> None:
        """Load current agenda from file."""
        try:
            if self._agenda_path.exists():
                self._agenda = self._agenda_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to load agenda: {e}")

    def save_agenda(self, content: str) -> None:
        """Save updated agenda to file."""
        try:
            self._agenda_path.parent.mkdir(parents=True, exist_ok=True)
            self._agenda_path.write_text(content, encoding="utf-8")
            self._agenda = content
            logger.info("Agenda updated")
        except Exception as e:
            logger.error(f"Failed to save agenda: {e}")

    def update_agenda_section(self, section: str, content: str) -> None:
        """Update a specific section in agenda."""
        lines = self._agenda.split("\n")
        new_lines = []
        in_section = False
        section_header = f"## {section}"

        for line in lines:
            if line.startswith("## "):
                if line == section_header:
                    in_section = True
                    new_lines.append(line)
                    new_lines.append(content)
                    continue
                else:
                    in_section = False
            if not in_section:
                new_lines.append(line)

        self.save_agenda("\n".join(new_lines))

    async def _load_user_profile(self) -> None:
        """Load user profile from core memory."""
        if not hasattr(self.memory, "get_core"):
            return

        name = await self.memory.get_core("user_name")
        if name:
            self._user_name = name

        context = await self.memory.get_core("user_context")
        if context:
            self._user_context = context

    async def process(self, message: Message) -> Message:
        """Process user message and generate response."""
        self.state = AgentState.ACTIVE
        logger.debug(f"DialogAgent processing: {message.content[:100]}...")

        self.context.conversation.append(message)
        self._trim_history()

        # Refresh agenda (might have been updated externally)
        self._load_agenda()

        # Retrieve relevant memories
        memories = await self._get_relevant_memories(message.content)
        memory_text = self._format_memories(memories)
        logger.debug(f"DialogAgent memories: {len(memories)} retrieved")

        # Build system prompt (without tool descriptions - tools passed via API)
        system_prompt = self.config.system_prompt.format(
            identity=self._identity,
            user_name=self._user_name,
            user_context=self._user_context or "(No additional context)",
            agenda=self._extract_agenda_summary(),
            memories=memory_text,
            tools="",  # Empty - tools passed via native API
        )
        logger.debug(f"DialogAgent system prompt: {len(system_prompt)} chars")

        llm_messages = [{"role": "system", "content": system_prompt}]
        for msg in self.context.conversation:
            llm_messages.append(msg.to_llm_format())
        logger.debug(f"DialogAgent conversation: {len(self.context.conversation)} messages")

        # Prepare tools for native API
        tools = None
        if self._tool_registry:
            # Convert to provider-specific format
            if self.llm.provider_type.value == "claude":
                tools = self._tool_registry.to_anthropic_tools()
            else:
                # OpenRouter, local, and others use OpenAI format
                tools = self._tool_registry.to_openai_tools()
            logger.debug(f"Prepared {len(tools)} tools for provider: {self.llm.provider_type.value}")

        llm_config = LLMConfig(model=None, max_tokens=2048, temperature=0.7)
        response = await self.llm.complete(llm_messages, llm_config, task=TaskType.CHAT, tools=tools)
        logger.debug(f"DialogAgent response: {len(response.content)} chars")

        # Check for native tool calls in response
        if self._tool_executor and response.tool_calls:
            tool_calls = response.tool_calls
            logger.info(f"Detected {len(tool_calls)} native tool call(s): {[tc['name'] for tc in tool_calls]}")

            # Convert native format to ToolCall objects for executor
            executor_calls = []
            for tc in tool_calls:
                executor_calls.append(
                    ToolCall(
                        tool_name=tc["name"],
                        arguments=tc["input"],
                        raw_json="",  # Not available for native calls
                    )
                )

            # Execute tools
            results = await self._tool_executor.execute_all(executor_calls)
            logger.debug(f"Tool execution results: {[r.success for r in results]}")

            # Format results back for provider
            if self.llm.provider_type.value == "claude":
                # Anthropic format: add assistant message, then user message with tool_result
                llm_messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                    # Note: Anthropic expects tool_use blocks in content, but we can't easily reconstruct
                    # For now, use simplified approach with text-based results
                })

                # Format tool results as text
                results_text = self._tool_executor.format_results_for_llm(results)
                llm_messages.append({
                    "role": "user",
                    "content": f"Tool results:\n\n{results_text}\n\nPlease provide a natural response based on these results.",
                })
            else:
                # OpenAI format: add assistant message with tool_calls, then tool messages
                llm_messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                })

                # Format tool results as text for now (simplified)
                results_text = self._tool_executor.format_results_for_llm(results)
                llm_messages.append({
                    "role": "user",
                    "content": f"Tool results:\n\n{results_text}\n\nPlease provide a natural response based on these results.",
                })

            # Get final natural language response from LLM (no tools this time)
            final_response = await self.llm.complete(
                llm_messages, llm_config, task=TaskType.CHAT, tools=None
            )
            logger.debug(f"DialogAgent final response: '{final_response.content[:100]}'")

            # Handle empty response
            if not final_response.content or not final_response.content.strip():
                logger.warning("Empty final response from LLM, formatting results directly")
                if results and results[0].success and results[0].data:
                    data = results[0].data
                    if "datetime" in data:
                        final_response.content = (
                            f"It's currently {data.get('time', '')} on "
                            f"{data.get('weekday', '')}, {data.get('date', '')}."
                        )
                    else:
                        final_response.content = f"Tool executed successfully: {data}"
                else:
                    final_response.content = results_text

            # Use final response
            response_msg = Message(
                id=str(uuid4()),
                timestamp=datetime.now(),
                role="assistant",
                content=final_response.content,
                content_type=ContentType.TEXT,
                metadata={
                    "model": final_response.model,
                    "tokens": final_response.input_tokens + final_response.output_tokens,
                    "cost_usd": final_response.cost_usd,
                    "tool_calls": len(tool_calls),
                    "tool_results": [r.success for r in results],
                },
            )
        else:
            # No tool calls, use original response
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
        await self._persist_exchange(message, response_msg)

        self.state = AgentState.READY
        return response_msg

    def _extract_agenda_summary(self) -> str:
        """Extract relevant agenda sections for context."""
        if not self._agenda:
            return "(No active agenda)"
        # Return first 500 chars of agenda as summary
        if len(self._agenda) > 500:
            return self._agenda[:500] + "..."
        return self._agenda

    async def _persist_exchange(self, user_msg: Message, assistant_msg: Message) -> None:
        """Save conversation exchange to episodic memory."""
        try:
            summary = f"User: {user_msg.content[:100]}"
            if len(user_msg.content) > 100:
                summary += "..."

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

    async def summarize_session(self) -> str | None:
        """Summarize and persist conversation, returns summary text."""
        if len(self.context.conversation) < 2:
            return None

        # Format conversation for summarization
        conv_text = "\n".join(
            f"{m.role}: {m.content[:500]}" for m in self.context.conversation[-20:]
        )

        # Use LLM to generate summary (uses cheaper model if available)
        llm_config = LLMConfig(model=None, max_tokens=256, temperature=0.3)
        messages = [{"role": "user", "content": SUMMARIZE_PROMPT.format(conversation=conv_text)}]

        try:
            response = await self.llm.complete(messages, llm_config, task=TaskType.SUMMARIZATION)
            summary = response.content.strip()

            # Score importance
            importance = await self._score_importance(summary)

            # Store as episodic memory
            entry = MemoryEntry(
                id=str(uuid4()),
                type=MemoryType.EPISODIC,
                content=summary,
                timestamp=datetime.now(),
                importance=importance,
                metadata={
                    "session_id": self.context.agent_id,
                    "msg_count": len(self.context.conversation),
                },
            )
            await self.memory.store(entry)

            logger.info(f"Session summarized (importance: {importance:.2f}): {summary[:100]}")
            return summary

        except Exception as e:
            logger.warning(f"Failed to summarize session: {e}")
            return None

    async def _score_importance(self, summary: str) -> float:
        """Score importance of a conversation summary (0.0-1.0)."""
        try:
            llm_config = LLMConfig(model=None, max_tokens=10, temperature=0.1)
            messages = [{"role": "user", "content": IMPORTANCE_PROMPT.format(summary=summary)}]
            response = await self.llm.complete(messages, llm_config, task=TaskType.IMPORTANCE_SCORING)

            # Parse the response - expect a number
            score_text = response.content.strip()
            score = float(score_text.split()[0])
            return max(0.0, min(1.0, score))
        except Exception:
            return 0.5  # Default importance
