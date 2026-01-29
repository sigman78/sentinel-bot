"""Code agent - writes and executes Python scripts in sandbox."""

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sentinel.agents.base import AgentConfig, AgentState, BaseAgent
from sentinel.core.config import get_settings
from sentinel.core.logging import get_logger
from sentinel.core.types import AgentType, ContentType, Message
from sentinel.agents.base import LLMProvider
from sentinel.llm.base import LLMConfig
from sentinel.llm.router import TaskType
from sentinel.memory.base import MemoryEntry, MemoryStore, MemoryType
from sentinel.workspace.executor import ScriptExecutor
from sentinel.workspace.manager import WorkspaceManager

logger = get_logger("agents.code")

WRITE_SCRIPT_PROMPT = """Write a Python script to accomplish this task: {task}

Requirements:
- Use Python 3.12+ syntax
- Include error handling
- Add brief comments
- Output results via print() statements
- Keep it simple and focused

Return ONLY the Python code, no explanations."""

ANALYZE_OUTPUT_PROMPT = """Analyze this script execution result and summarize for the user.

Task: {task}
Exit code: {exit_code}
Output:
{output}

Error output:
{stderr}

Provide a clear summary of what happened and whether the task succeeded."""


class CodeAgent(BaseAgent):
    """Agent that writes and executes Python code in a sandbox."""

    def __init__(
        self,
        llm: LLMProvider,
        memory: MemoryStore,
        workspace_manager: WorkspaceManager | None = None,
    ):
        config = AgentConfig(
            agent_type=AgentType.CODE,
            system_prompt="Python code execution agent",
            timeout_seconds=600.0,
        )
        super().__init__(config, llm, memory)

        settings = get_settings()
        self._workspace = workspace_manager or WorkspaceManager(settings.workspace_dir)
        self._executor = ScriptExecutor(self._workspace)

    async def initialize(self) -> None:
        """Initialize workspace environment."""
        await super().initialize()
        await self._workspace.initialize()
        logger.info("CodeAgent initialized")

    async def process(self, message: Message) -> Message:
        """Process code request: write script, execute, return results."""
        self.state = AgentState.ACTIVE
        task = message.content

        try:
            # Step 1: Generate script using LLM
            script_content = await self._generate_script(task)

            # Step 2: Save script to workspace
            script_path = await self._workspace.save_script(
                script_content, prefix=f"task_{message.id[:8]}"
            )
            logger.info(f"Script saved: {script_path}")

            # Step 3: Execute in sandbox
            result = await self._executor.execute(script_path)

            # Step 4: Analyze results
            summary = await self._analyze_result(task, result)

            # Step 5: Store execution in memory
            await self._persist_execution(task, script_path, result)

            response_content = f"{summary}\n\nScript: {script_path.name}"

        except Exception as e:
            logger.error(f"Code execution failed: {e}", exc_info=True)
            response_content = f"Code execution failed: {str(e)}"

        self.state = AgentState.READY
        return Message(
            id=str(uuid4()),
            timestamp=datetime.now(),
            role="assistant",
            content=response_content,
            content_type=ContentType.TEXT,
        )

    async def _generate_script(self, task: str) -> str:
        """Use LLM to generate Python script for task."""
        llm_config = LLMConfig(model=None, max_tokens=2048, temperature=0.2)
        messages = [{"role": "user", "content": WRITE_SCRIPT_PROMPT.format(task=task)}]

        response = await self.llm.complete(messages, llm_config, task=TaskType.TOOL_CALL)

        # Extract code from markdown blocks if present
        code = response.content.strip()
        if code.startswith("```python"):
            code = code.split("```python")[1].split("```")[0].strip()
        elif code.startswith("```"):
            code = code.split("```")[1].split("```")[0].strip()

        return code

    async def _analyze_result(self, task: str, result) -> str:
        """Use LLM to analyze execution results."""
        llm_config = LLMConfig(model=None, max_tokens=512, temperature=0.3)
        messages = [
            {
                "role": "user",
                "content": ANALYZE_OUTPUT_PROMPT.format(
                    task=task,
                    exit_code=result.exit_code,
                    output=result.output[:1000],
                    stderr=result.stderr[:500] if result.stderr else "(none)",
                ),
            }
        ]

        response = await self.llm.complete(
            messages, llm_config, task=TaskType.SUMMARIZATION
        )
        return response.content.strip()

    async def _persist_execution(self, task: str, script_path: Path, result) -> None:
        """Save execution to episodic memory."""
        try:
            status = "success" if result.exit_code == 0 else "failed"
            summary = f"Code execution ({status}): {task[:100]}"

            entry = MemoryEntry(
                id=str(uuid4()),
                type=MemoryType.EPISODIC,
                content=summary,
                timestamp=datetime.now(),
                importance=0.6,
                metadata={
                    "agent_type": "code",
                    "task": task,
                    "script": str(script_path),
                    "exit_code": result.exit_code,
                    "duration_ms": result.duration_ms,
                },
            )
            await self.memory.store(entry)
        except Exception as e:
            logger.warning(f"Failed to persist execution: {e}")

    async def terminate(self) -> None:
        """Clean up workspace resources."""
        await self._workspace.cleanup_temp()
        await super().terminate()
