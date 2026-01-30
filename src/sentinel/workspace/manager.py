"""Workspace directory lifecycle and file management."""

import shutil
from datetime import datetime, timedelta
from pathlib import Path

from sentinel.core.logging import get_logger

logger = get_logger("workspace.manager")


class WorkspaceManager:
    """Manages workspace directory structure and file lifecycle."""

    def __init__(self, workspace_dir: Path):
        self.root = workspace_dir
        self.scripts_dir = self.root / "scripts"
        self.output_dir = self.root / "output"
        self.temp_dir = self.root / "temp"
        self.venv_dir = self.root / ".venv"

        # Safety limits
        self._max_script_size = 100_000  # 100KB
        self._max_output_size = 10_000_000  # 10MB
        self._script_retention_days = 30

    async def initialize(self) -> None:
        """Create workspace structure and virtual environment."""
        # Create directories
        for directory in [self.scripts_dir, self.output_dir, self.temp_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        # Create venv if missing
        if not (self.venv_dir / "pyvenv.cfg").exists():
            await self._create_venv()

        logger.info(f"Workspace initialized at {self.root}")

    async def _create_venv(self) -> None:
        """Create isolated virtual environment."""
        import asyncio
        import sys

        logger.info("Creating workspace virtual environment...")
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "venv",
            str(self.venv_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()

        if proc.returncode == 0:
            logger.info("Virtual environment created")
        else:
            raise RuntimeError("Failed to create virtual environment")

    async def save_script(self, content: str, prefix: str = "script") -> Path:
        """Save script to workspace with validation."""
        if len(content.encode("utf-8")) > self._max_script_size:
            raise ValueError(f"Script exceeds size limit ({self._max_script_size} bytes)")

        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.py"
        script_path = self.scripts_dir / filename

        # Write with UTF-8 encoding
        script_path.write_text(content, encoding="utf-8")
        logger.debug(f"Script saved: {script_path}")

        return script_path

    async def save_output(self, script_name: str, output: str) -> Path:
        """Save script output to file."""
        output_path = self.output_dir / f"{script_name}.txt"

        # Truncate if too large
        if len(output.encode("utf-8")) > self._max_output_size:
            logger.warning(f"Output truncated to {self._max_output_size} bytes")
            output = output[: self._max_output_size]

        output_path.write_text(output, encoding="utf-8")
        return output_path

    async def cleanup_temp(self) -> None:
        """Remove temporary files."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            self.temp_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("Temp directory cleaned")

    async def cleanup_old_scripts(self) -> int:
        """Remove scripts older than retention period."""
        cutoff = datetime.now() - timedelta(days=self._script_retention_days)
        removed = 0

        for script in self.scripts_dir.glob("*.py"):
            mtime = datetime.fromtimestamp(script.stat().st_mtime)
            if mtime < cutoff:
                script.unlink()
                removed += 1

        if removed > 0:
            logger.info(f"Cleaned up {removed} old scripts")

        return removed

    def get_python_path(self) -> Path:
        """Get path to workspace Python interpreter."""
        import sys

        if sys.platform == "win32":
            return self.venv_dir / "Scripts" / "python.exe"
        return self.venv_dir / "bin" / "python"

    def is_path_safe(self, path: Path) -> bool:
        """Check if path is within workspace boundaries."""
        try:
            path.resolve().relative_to(self.root.resolve())
            return True
        except ValueError:
            return False
