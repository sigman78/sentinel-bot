"""Tool agent - stateless specialized agents that wrap tools with reasoning."""

from abc import abstractmethod
from datetime import datetime
from uuid import uuid4

from sentinel.agents.base import AgentConfig, AgentState, BaseAgent
from sentinel.core.logging import get_logger
from sentinel.core.types import AgentType, ContentType, Message
from sentinel.agents.base import LLMProvider

logger = get_logger("agents.tool_agent")


class ToolAgent(BaseAgent):
    """Base class for stateless tool agents.

    Tool agents:
    - Wrap specific tool(s) with specialized reasoning
    - Execute single-call tasks without state persistence
    - Present natural language capabilities to parent agents
    - Use cheaper/faster LLMs for focused reasoning
    """

    # Override in subclass
    capability_description: str = "Generic tool agent"
    agent_name: str = "ToolAgent"

    def __init__(self, llm: LLMProvider):
        """Initialize tool agent.

        Args:
            llm: LLM provider (lazy-initialized, may not connect until first use)
        """
        config = AgentConfig(
            agent_type=AgentType.DIALOG,  # Reuse type for now
            system_prompt="",  # Built per-call
            timeout_seconds=30.0,
        )
        # Note: memory=None because tool agents are stateless
        super().__init__(config, llm, memory=None)
        self._llm_initialized = False

    async def process(self, message: Message) -> Message:
        """Process a single task - main entry point for delegation.

        Args:
            message: Contains task description and global context in metadata

        Returns:
            Message with natural language result or error
        """
        self.state = AgentState.ACTIVE
        task = message.content
        global_context = message.metadata.get("global_context", {})

        logger.info(f"{self.agent_name} processing: {task[:100]}")

        try:
            # Execute task with specialized logic
            result = await self.execute_task(task, global_context)

            response = Message(
                id=str(uuid4()),
                timestamp=datetime.now(),
                role="assistant",
                content=result,
                content_type=ContentType.TEXT,
                metadata={"agent": self.agent_name},
            )
        except Exception as e:
            logger.error(f"{self.agent_name} execution failed: {e}", exc_info=True)
            response = Message(
                id=str(uuid4()),
                timestamp=datetime.now(),
                role="assistant",
                content=f"Error: {str(e)}",
                content_type=ContentType.TEXT,
                metadata={"agent": self.agent_name, "error": True},
            )

        self.state = AgentState.READY
        return response

    @abstractmethod
    async def execute_task(self, task: str, global_context: dict) -> str:
        """Execute the specialized task.

        Override this method in subclasses to implement tool-specific logic.

        Args:
            task: Natural language task description from parent agent
            global_context: Shared context (user_profile, etc.)

        Returns:
            Natural language result string

        Raises:
            Exception: On execution failure (caught by process())
        """
        ...

    async def _ensure_llm_initialized(self) -> None:
        """Lazy initialization of LLM resources."""
        if not self._llm_initialized:
            # LLM providers typically connect on first use
            # Could add explicit connect() call here if needed
            self._llm_initialized = True
            logger.debug(f"{self.agent_name} LLM initialized")

    def get_capability_description(self) -> str:
        """Return natural language description of capabilities.

        Used by parent agents to understand what this tool agent can do.
        """
        return self.capability_description
