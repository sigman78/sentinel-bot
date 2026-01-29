"""Agentic CLI agent - autonomous task execution with CLI tools."""

import asyncio
import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from sentinel.agents.base import AgentConfig, AgentState, BaseAgent
from sentinel.core.logging import get_logger
from sentinel.core.types import AgentType, ContentType, Message
from sentinel.agents.base import LLMProvider
from sentinel.llm.base import LLMConfig
from sentinel.llm.router import TaskType

logger = get_logger("agents.agentic_cli")


@dataclass
class SafetyLimits:
    """Safety constraints for agentic loops."""

    timeout_seconds: float = 120.0
    max_iterations: int = 20
    max_consecutive_errors: int = 3
    max_total_errors: int = 5


@dataclass
class CliTool:
    """CLI tool definition using natural language documentation."""

    name: str
    command: str  # Base command (e.g., "git", "docker", "curl")
    help_text: str | None = None
    examples: list[str] = field(default_factory=list)

    @classmethod
    def from_command(
        cls,
        name: str,
        command: str,
        auto_help: bool = True,
        examples: list[str] | None = None,
    ) -> "CliTool":
        """Auto-generate tool from CLI help output.

        Args:
            name: Tool name for identification
            command: Base command to execute
            auto_help: Whether to auto-fetch help text
            examples: Example commands

        Returns:
            CliTool instance with help text populated
        """
        help_text = None

        if auto_help:
            # Try common help flags
            for flag in ["--help", "-h", "help"]:
                try:
                    result = subprocess.run(
                        [command, flag],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if result.returncode == 0 and result.stdout:
                        help_text = result.stdout
                        break
                except Exception:
                    continue

        return cls(
            name=name, command=command, help_text=help_text, examples=examples or []
        )

    def to_llm_context(self) -> str:
        """Format tool documentation for LLM context."""
        parts = [f"## Tool: {self.name}"]
        parts.append(f"Base command: `{self.command}`")

        if self.help_text:
            parts.append("\nHelp documentation:")
            parts.append("```")
            # Limit size to avoid context bloat
            parts.append(self.help_text[:2000])
            if len(self.help_text) > 2000:
                parts.append("... (truncated)")
            parts.append("```")

        if self.examples:
            parts.append("\nExample usage:")
            for ex in self.examples:
                parts.append(f"  $ {ex}")

        return "\n".join(parts)


@dataclass
class AgenticCliConfig:
    """Configuration for an agentic CLI agent."""

    name: str
    description: str  # Natural language capability description
    tools: list[CliTool]
    limits: SafetyLimits = field(default_factory=SafetyLimits)


@dataclass
class CommandResult:
    """Result of executing a CLI command."""

    command: str
    stdout: str
    stderr: str
    exit_code: int
    success: bool
    duration_ms: float


@dataclass
class Step:
    """Single step in the agentic loop."""

    iteration: int
    command: str
    result: CommandResult
    timestamp: datetime


@dataclass
class ErrorRecord:
    """Record of an error during execution."""

    iteration: int
    command: str
    message: str
    timestamp: datetime


@dataclass
class AgenticLoopState:
    """State maintained across loop iterations."""

    goal: str
    steps_completed: list[Step] = field(default_factory=list)
    errors_encountered: list[ErrorRecord] = field(default_factory=list)
    current_iteration: int = 0
    start_time: datetime = field(default_factory=datetime.now)

    def to_prompt_context(self) -> str:
        """Format state for LLM context."""
        ctx = [f"GOAL: {self.goal}"]
        ctx.append(f"ITERATION: {self.current_iteration}")

        if self.steps_completed:
            ctx.append("\nSTEPS COMPLETED:")
            # Show last 5 steps to avoid context bloat
            for step in self.steps_completed[-5:]:
                status = "✓" if step.result.success else "✗"
                output = step.result.stdout if step.result.success else step.result.stderr
                # Truncate output
                output_preview = output[:100].replace("\n", " ")
                if len(output) > 100:
                    output_preview += "..."
                ctx.append(f"  {status} `{step.command}` → {output_preview}")

        if self.errors_encountered:
            ctx.append(f"\nERRORS ENCOUNTERED: {len(self.errors_encountered)}")
            # Show last 3 errors
            for err in self.errors_encountered[-3:]:
                ctx.append(f"  - `{err.command}`: {err.message[:100]}")

        return "\n".join(ctx)

    def elapsed_seconds(self) -> float:
        """Get elapsed time since start."""
        return (datetime.now() - self.start_time).total_seconds()

    def consecutive_error_count(self) -> int:
        """Count consecutive errors from the end."""
        if not self.errors_encountered:
            return 0

        count = 0
        for i in range(len(self.errors_encountered) - 1, -1, -1):
            err = self.errors_encountered[i]
            # Check if this error is from the most recent iterations
            if err.iteration >= self.current_iteration - count:
                count += 1
            else:
                break
        return count


AGENTIC_CLI_SYSTEM = """You are {agent_name}: {agent_description}

You execute tasks autonomously by calling CLI tools. Respond with JSON showing your reasoning and next action.

## Current State

{state_context}

## Safety Limits
- Max iterations: {max_iterations}
- Max consecutive errors: {max_consecutive_errors}
- Timeout: {timeout_seconds}s

## Available Tools

{tools_context}

## Response Format

You MUST respond with valid JSON in this exact format:

{{
  "thinking": "analyze current state and decide what to do next",
  "action": {{
    "type": "call" | "done",
    "command": "full CLI command to execute",  // if type=call
    "status": "success" | "error",             // if type=done
    "result": "summary of what was accomplished or error message"  // if type=done
  }}
}}

## Guidelines

 - Use only the CLI tools advertised by the agent. Fail if the job cannot be accomplished with the provided tools or if any required tool is unavailable.
 - Execute ONE command at a time based on current state. 
 - You may pipe CLI command output into platform's common filter, trim, sort, grep commands to keep output relevant and lean.
 - Add 'non interactive' options for CLI commands, if necessary, but be mindful about dangerous operations.
 - Be aware of environment/shell you are operating on - windows, linux, wsl, freebsd, etc.
 - Use full CLI syntax - the command will be executed in a shell
 - Analyze stdout/stderr from previous commands before next step
 - After errors, try 1-2 alternative approaches, then give up
 - "Not found" or "no results" IS a valid answer - call done with the negative result
 - When goal is accomplished OR cannot be completed, set action.type="done"
 - Be concise in results - summarize key outcomes


IMPORTANT: If you've tried 2-3 different approaches and all failed with "not found" or similar,
the answer is simply "nothing found" - call done with that result. Don't keep retrying endlessly.

## Examples

Step 1 - Initial exploration:
{{
  "thinking": "Need to check current status before proceeding",
  "action": {{"type": "call", "command": "ls -la"}}
}}

Step 2 - After seeing output:
{{
  "thinking": "Found 3 files. Need to examine main.py contents",
  "action": {{"type": "call", "command": "cat main.py"}}
}}

Final - Task complete:
{{
  "thinking": "Successfully completed all required steps",
  "action": {{
    "type": "done",
    "status": "success",
    "result": "Analyzed 3 files and found the target function in main.py"
  }}
}}

Error case - Cannot proceed:
{{
  "thinking": "Tried 3 different approaches but file not found",
  "action": {{
    "type": "done",
    "status": "error",
    "result": "Cannot complete task: target file does not exist"
  }}
}}

Negative result case - Valid answer:
{{
  "thinking": "Searched with 'dir *.py' and got 'File Not Found' - this means no Python files exist",
  "action": {{
    "type": "done",
    "status": "success",
    "result": "No Python files found in the current directory"
  }}
}}
"""


class AgenticCliAgent(BaseAgent):
    """Autonomous agent that executes CLI commands in a loop until task completion.

    Features:
    - Self-enforced safety limits (timeout, iterations, errors)
    - Structured JSON output for parsing
    - State tracking across loop iterations
    - Natural language tool documentation
    """

    agent_name: str = "AgenticCliAgent"
    capability_description: str = "Generic CLI tool agent"

    def __init__(
        self, config: AgenticCliConfig, llm: LLMProvider, working_dir: str | None = None
    ):
        """Initialize agentic CLI agent.

        Args:
            config: Agent configuration with tools and limits
            llm: LLM provider for decision making
            working_dir: Working directory for command execution (default: current dir)
        """
        agent_config = AgentConfig(
            agent_type=AgentType.DIALOG,  # Reuse type for now
            system_prompt=AGENTIC_CLI_SYSTEM,
            timeout_seconds=config.limits.timeout_seconds,
        )
        super().__init__(agent_config, llm, memory=None)

        self.agent_name = config.name
        self.capability_description = config.description
        self.cli_tools = config.tools
        self.limits = config.limits
        self.working_dir = working_dir

    async def process(self, message: Message) -> Message:
        """Execute task with autonomous CLI loop and internal safety enforcement.

        Args:
            message: Contains task description

        Returns:
            Message with result or error
        """
        self.state = AgentState.ACTIVE
        task = message.content
        loop_state = AgenticLoopState(goal=task)

        logger.info(f"{self.agent_name} starting task: {task}")

        try:
            while True:
                # SAFETY LIMIT 1: Timeout
                if loop_state.elapsed_seconds() >= self.limits.timeout_seconds:
                    logger.warning(f"{self.agent_name} timeout after {loop_state.elapsed_seconds():.1f}s")
                    return self._create_error_response(
                        f"Task timeout after {self.limits.timeout_seconds}s"
                    )

                # SAFETY LIMIT 2: Max iterations
                if loop_state.current_iteration >= self.limits.max_iterations:
                    logger.warning(f"{self.agent_name} max iterations reached")
                    return self._create_error_response(
                        f"Max iterations ({self.limits.max_iterations}) exceeded"
                    )

                # SAFETY LIMIT 3: Consecutive errors
                consecutive_errors = loop_state.consecutive_error_count()
                if consecutive_errors >= self.limits.max_consecutive_errors:
                    logger.warning(f"{self.agent_name} too many consecutive errors")
                    return self._create_error_response(
                        f"Too many consecutive errors ({consecutive_errors})"
                    )

                # SAFETY LIMIT 4: Total errors
                if len(loop_state.errors_encountered) >= self.limits.max_total_errors:
                    logger.warning(f"{self.agent_name} total error limit reached")
                    return self._create_error_response(
                        f"Too many total errors ({self.limits.max_total_errors})"
                    )

                # Get next action from LLM
                decision = await self._get_next_action(loop_state)

                logger.info(
                    f"Iteration {loop_state.current_iteration}: {decision['thinking'][:100]}"
                )

                action = decision["action"]

                # Check for task completion
                if action["type"] == "done":
                    status = action["status"]
                    result = action["result"]

                    logger.info(f"{self.agent_name} finished: {status} - {result[:100]}")

                    if status == "success":
                        return self._create_success_response(result)
                    else:
                        return self._create_error_response(result)

                # Execute CLI command
                elif action["type"] == "call":
                    command = action["command"]
                    cmd_result = await self._execute_command(command)

                    # Record step
                    step = Step(
                        iteration=loop_state.current_iteration,
                        command=command,
                        result=cmd_result,
                        timestamp=datetime.now(),
                    )
                    loop_state.steps_completed.append(step)

                    # Track errors
                    if not cmd_result.success:
                        error = ErrorRecord(
                            iteration=loop_state.current_iteration,
                            command=command,
                            message=cmd_result.stderr or f"Exit code {cmd_result.exit_code}",
                            timestamp=datetime.now(),
                        )
                        loop_state.errors_encountered.append(error)
                        logger.warning(f"Command failed: {command} - {error.message[:100]}")

                loop_state.current_iteration += 1

        except Exception as e:
            logger.error(f"{self.agent_name} execution failed: {e}", exc_info=True)
            return self._create_error_response(f"Execution error: {str(e)}")
        finally:
            self.state = AgentState.READY

    async def _get_next_action(self, loop_state: AgenticLoopState) -> dict[str, Any]:
        """Get next action from LLM with structured output.

        Args:
            loop_state: Current loop state

        Returns:
            Parsed JSON with thinking and action
        """
        # Build tools context
        tools_context = "\n\n".join(tool.to_llm_context() for tool in self.cli_tools)

        # Build system prompt
        system_prompt = self.config.system_prompt.format(
            agent_name=self.agent_name,
            agent_description=self.capability_description,
            state_context=loop_state.to_prompt_context(),
            max_iterations=self.limits.max_iterations,
            max_consecutive_errors=self.limits.max_consecutive_errors,
            timeout_seconds=self.limits.timeout_seconds,
            tools_context=tools_context,
        )

        # Build user message prompting for next action
        user_prompt = "What should be the next action? Respond with JSON."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # Request JSON output
        llm_config = LLMConfig(
            model=None,
            max_tokens=1024,
            temperature=0.3,
        )

        response = await self.llm.complete(messages, llm_config, task=TaskType.TOOL_CALL)

        # Parse JSON from response
        content = response.content.strip()

        # Handle markdown code blocks
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first and last lines (```)
            content = "\n".join(lines[1:-1])
            if content.startswith("json"):
                content = content[4:].strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {content[:200]}")
            raise ValueError(f"Invalid JSON response from LLM: {e}")

    async def _execute_command(self, command: str) -> CommandResult:
        """Execute CLI command in subprocess.

        Args:
            command: Full command string to execute

        Returns:
            CommandResult with stdout, stderr, exit code
        """
        logger.debug(f"Executing: {command}")
        start_time = datetime.now()

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.working_dir,
            )

            # Wait with timeout (per-command limit)
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=30.0
            )

            duration_ms = (datetime.now() - start_time).total_seconds() * 1000

            return CommandResult(
                command=command,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                exit_code=process.returncode or 0,
                success=process.returncode == 0,
                duration_ms=duration_ms,
            )

        except asyncio.TimeoutError:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            return CommandResult(
                command=command,
                stdout="",
                stderr="Command timeout (30s)",
                exit_code=-1,
                success=False,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            return CommandResult(
                command=command,
                stdout="",
                stderr=f"Execution error: {str(e)}",
                exit_code=-1,
                success=False,
                duration_ms=duration_ms,
            )

    def _create_success_response(self, result: str) -> Message:
        """Create success response message."""
        return Message(
            id=str(uuid4()),
            timestamp=datetime.now(),
            role="assistant",
            content=result,
            content_type=ContentType.TEXT,
            metadata={"agent": self.agent_name, "status": "success"},
        )

    def _create_error_response(self, error: str) -> Message:
        """Create error response message."""
        return Message(
            id=str(uuid4()),
            timestamp=datetime.now(),
            role="assistant",
            content=f"Error: {error}",
            content_type=ContentType.TEXT,
            metadata={"agent": self.agent_name, "error": True},
        )

    def get_capability_description(self) -> str:
        """Return capability description for parent agents."""
        return self.capability_description
