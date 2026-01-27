"""Sleep agent - runs during idle to consolidate memories and extract facts."""

from datetime import datetime, timedelta
from uuid import uuid4

from sentinel.agents.base import AgentConfig, AgentState, BaseAgent
from sentinel.core.logging import get_logger
from sentinel.core.types import AgentType, ContentType, Message
from sentinel.llm.base import LLMConfig, LLMProvider
from sentinel.llm.router import TaskType
from sentinel.memory.base import MemoryEntry, MemoryStore, MemoryType

logger = get_logger("agents.sleep")

EXTRACT_FACTS_PROMPT = """Analyze these conversation summaries and extract durable facts.
Focus on: user preferences, personal details, recurring topics, decisions made, important dates.
Return facts as a JSON array of strings, one fact per item.

Summaries:
{summaries}

Facts (JSON array):"""

CONSOLIDATE_PROMPT = """These conversation summaries describe related interactions.
Create a single consolidated summary that preserves key information but is more concise.

Summaries:
{summaries}

Consolidated summary (2-3 sentences):"""


class SleepAgent(BaseAgent):
    """Background agent that consolidates memories during idle time."""

    def __init__(self, llm: LLMProvider, memory: MemoryStore):
        config = AgentConfig(
            agent_type=AgentType.SLEEP,
            system_prompt="Memory consolidation agent",
        )
        super().__init__(config, llm, memory)
        self._consolidation_window = timedelta(days=7)
        self._min_memories_to_consolidate = 5

    async def process(self, message: Message) -> Message:
        """Not used - sleep agent runs autonomously."""
        return Message(
            id=str(uuid4()),
            timestamp=datetime.now(),
            role="assistant",
            content="Sleep agent does not process messages directly.",
            content_type=ContentType.TEXT,
        )

    async def run_consolidation(self) -> dict:
        """Main consolidation routine - run during idle."""
        self.state = AgentState.ACTIVE
        result = {"facts_extracted": 0, "memories_consolidated": 0}

        try:
            # Get recent episodic memories
            if not hasattr(self.memory, "get_recent"):
                return result

            recent = await self.memory.get_recent(limit=20)
            if len(recent) < self._min_memories_to_consolidate:
                logger.debug("Not enough memories to consolidate")
                return result

            # Extract facts from summaries
            facts = await self._extract_facts(recent)
            result["facts_extracted"] = len(facts)

            # Store extracted facts as semantic memory
            for fact in facts:
                entry = MemoryEntry(
                    id=str(uuid4()),
                    type=MemoryType.SEMANTIC,
                    content=fact,
                    timestamp=datetime.now(),
                    importance=0.7,
                    metadata={"source": "sleep_consolidation"},
                )
                await self.memory.store(entry)

            logger.info(f"Sleep: extracted {len(facts)} facts")

        except Exception as e:
            logger.error(f"Consolidation failed: {e}")

        self.state = AgentState.READY
        return result

    async def _extract_facts(self, memories: list[MemoryEntry]) -> list[str]:
        """Extract durable facts from memory summaries."""
        summaries = "\n".join(f"- {m.content}" for m in memories)

        llm_config = LLMConfig(model=None, max_tokens=500, temperature=0.3)
        messages = [{"role": "user", "content": EXTRACT_FACTS_PROMPT.format(summaries=summaries)}]

        try:
            response = await self.llm.complete(messages, llm_config, task=TaskType.FACT_EXTRACTION)
            content = response.content.strip()

            # Parse JSON array from response
            import json
            # Handle common LLM output patterns
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            facts = json.loads(content)
            return facts if isinstance(facts, list) else []

        except Exception as e:
            logger.warning(f"Fact extraction failed: {e}")
            return []

    async def _consolidate_related(self, memories: list[MemoryEntry]) -> str | None:
        """Consolidate related memories into a single summary."""
        if len(memories) < 2:
            return None

        summaries = "\n".join(f"- {m.content}" for m in memories)

        llm_config = LLMConfig(model=None, max_tokens=256, temperature=0.3)
        messages = [{"role": "user", "content": CONSOLIDATE_PROMPT.format(summaries=summaries)}]

        try:
            response = await self.llm.complete(messages, llm_config, task=TaskType.SUMMARIZATION)
            return response.content.strip()
        except Exception as e:
            logger.warning(f"Consolidation failed: {e}")
            return None
