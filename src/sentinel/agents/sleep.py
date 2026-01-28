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
        """Main consolidation routine - run during idle.

        Consolidation pipeline:
        1. Extract facts from recent memories (semantic memory)
        2. Find and consolidate similar/redundant episodes
        3. Apply importance decay to old memories
        """
        self.state = AgentState.ACTIVE
        result = {"facts_extracted": 0, "memories_consolidated": 0, "memories_decayed": 0}

        try:
            # Get recent episodic memories
            if not hasattr(self.memory, "get_recent"):
                return result

            recent = await self.memory.get_recent(limit=20)
            if len(recent) < self._min_memories_to_consolidate:
                logger.debug("Not enough memories to consolidate")
                return result

            # Phase 1: Extract facts from summaries
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

            # Phase 2: Consolidate similar episodes
            similar_groups = self._group_similar_memories(recent)
            for group in similar_groups:
                if len(group) >= 2:  # Only consolidate if 2+ similar memories
                    consolidated = await self._consolidate_related(group)
                    if consolidated:
                        # Store consolidated version
                        consolidated_entry = MemoryEntry(
                            id=str(uuid4()),
                            type=MemoryType.EPISODIC,
                            content=consolidated,
                            timestamp=datetime.now(),
                            importance=max(m.importance for m in group),  # Keep highest importance
                            metadata={
                                "consolidated_from": [m.id for m in group],
                                "source": "sleep_consolidation",
                            },
                        )
                        await self.memory.store(consolidated_entry)

                        # Mark originals as consolidated (lower importance dramatically)
                        for memory in group:
                            await self.memory.update(memory.id, importance=0.1)

                        result["memories_consolidated"] += len(group)

            logger.info(f"Sleep: consolidated {result['memories_consolidated']} memories")

            # Phase 3: Apply importance decay to old memories
            decay_count = await self._decay_old_memories()
            result["memories_decayed"] = decay_count

        except Exception as e:
            logger.error(f"Consolidation failed: {e}")

        self.state = AgentState.READY
        return result

    def _group_similar_memories(self, memories: list[MemoryEntry]) -> list[list[MemoryEntry]]:
        """Group memories by similarity using simple heuristics.

        Groups memories that:
        - Share significant keywords (>50% overlap)
        - Are within same time window (within 7 days)
        """
        groups = []
        used = set()

        for i, mem1 in enumerate(memories):
            if mem1.id in used:
                continue

            # Start a new group
            group = [mem1]
            used.add(mem1.id)

            # Find similar memories
            mem1_words = set(mem1.content.lower().split())

            for mem2 in memories[i + 1 :]:
                if mem2.id in used:
                    continue

                # Check keyword overlap
                mem2_words = set(mem2.content.lower().split())
                overlap = len(mem1_words & mem2_words)
                total = len(mem1_words | mem2_words)
                similarity = overlap / total if total > 0 else 0

                # Check time proximity
                time_diff = abs((mem1.timestamp - mem2.timestamp).days)

                # Group if similar and recent (>= 50% keyword overlap)
                if similarity >= 0.5 and time_diff <= 7:
                    group.append(mem2)
                    used.add(mem2.id)

            # Only keep groups with 2+ memories
            if len(group) >= 2:
                groups.append(group)

        return groups

    async def _decay_old_memories(self) -> int:
        """Apply importance decay to memories older than consolidation window.

        Reduces importance of old episodic memories to prioritize recent context.
        """
        decay_count = 0

        try:
            # Get old memories (older than consolidation window)
            old_date = datetime.now() - self._consolidation_window

            # Note: This requires adding a method to MemoryStore
            # For now, skip this as it needs schema changes
            # In future: await self.memory.decay_importance_before(old_date, factor=0.8)

            logger.debug("Importance decay skipped (needs schema extension)")

        except Exception as e:
            logger.warning(f"Importance decay failed: {e}")

        return decay_count

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
