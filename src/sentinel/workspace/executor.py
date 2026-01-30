"""Safe Python script execution with timeout and resource limits."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from time import time

from sentinel.core.logging import get_logger
from sentinel.workspace.manager import WorkspaceManager

logger = get_logger("workspace.executor")


@dataclass
class ExecutionResult:
    """Result of script execution."""

    exit_code: int
    output: str
    stderr: str
    duration_ms: int
    timed_out: bool = False
    error: str | None = None


class ScriptExecutor:
    """Executes Python scripts in sandboxed environment."""

    def __init__(self, workspace: WorkspaceManager):
        self.workspace = workspace
        self._timeout_seconds = 30.0  # Default timeout
        self._max_output_bytes = 1_000_000  # 1MB output limit

    async def execute(self, script_path: Path, timeout: float | None = None) -> ExecutionResult:
        """Execute script with safety constraints."""
        # Validate script is in workspace
        if not self.workspace.is_path_safe(script_path):
            raise ValueError(f"Script path outside workspace: {script_path}")

        if not script_path.exists():
            raise FileNotFoundError(f"Script not found: {script_path}")

        timeout = timeout or self._timeout_seconds
        python_path = self.workspace.get_python_path()

        logger.info(f"Executing {script_path.name} (timeout: {timeout}s)")
        start_time = time()

        try:
            # Run script in subprocess with constraints
            proc = await asyncio.create_subprocess_exec(
                str(python_path),
                str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace.root),  # Set working directory to workspace
            )

            # Wait with timeout
            try:
                stdout_data, stderr_data = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
                timed_out = False
            except TimeoutError:
                proc.kill()
                await proc.wait()
                stdout_data = b"(execution timed out)"
                stderr_data = b""
                timed_out = True

            duration_ms = int((time() - start_time) * 1000)

            # Decode output with size limits
            output = self._decode_output(stdout_data)
            stderr = self._decode_output(stderr_data)

            # Save output to file
            if output:
                await self.workspace.save_output(script_path.stem, output)

            result = ExecutionResult(
                exit_code=proc.returncode if proc.returncode is not None else -1,
                output=output,
                stderr=stderr,
                duration_ms=duration_ms,
                timed_out=timed_out,
            )

            logger.info(
                f"Execution complete: exit={result.exit_code}, "
                f"duration={duration_ms}ms, timed_out={timed_out}"
            )
            return result

        except Exception as e:
            logger.error(f"Execution failed: {e}", exc_info=True)
            return ExecutionResult(
                exit_code=-1,
                output="",
                stderr="",
                duration_ms=int((time() - start_time) * 1000),
                error=str(e),
            )

    def _decode_output(self, data: bytes) -> str:
        """Decode output bytes with size limit."""
        if len(data) > self._max_output_bytes:
            logger.warning(f"Output truncated to {self._max_output_bytes} bytes")
            data = data[: self._max_output_bytes]

        try:
            return data.decode("utf-8", errors="replace")
        except Exception:
            return data.decode("latin-1", errors="replace")
