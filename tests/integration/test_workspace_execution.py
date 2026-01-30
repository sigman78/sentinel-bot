"""Integration tests for workspace script execution (requires venv creation)."""

from pathlib import Path

import pytest

from sentinel.workspace.executor import ScriptExecutor
from sentinel.workspace.manager import WorkspaceManager


@pytest.fixture
async def workspace(tmp_path: Path):
    """Create temporary workspace with venv (slow)."""
    ws = WorkspaceManager(tmp_path / "workspace")
    await ws.initialize()
    return ws


@pytest.mark.asyncio
async def test_workspace_venv_creation(workspace: WorkspaceManager):
    """Virtual environment is created."""
    assert workspace.venv_dir.exists()
    assert (workspace.venv_dir / "pyvenv.cfg").exists()


@pytest.mark.asyncio
async def test_get_python_path(workspace: WorkspaceManager):
    """Python path is correct."""
    python_path = workspace.get_python_path()

    assert python_path.exists()
    assert python_path.is_file()
    assert "python" in python_path.name.lower()


@pytest.mark.asyncio
async def test_execute_simple_script(workspace: WorkspaceManager):
    """Simple script execution succeeds."""
    script = "print('Hello from test')"
    script_path = await workspace.save_script(script, prefix="hello")

    executor = ScriptExecutor(workspace)
    result = await executor.execute(script_path)

    assert result.exit_code == 0
    assert "Hello from test" in result.output
    assert not result.timed_out
    assert result.duration_ms > 0


@pytest.mark.asyncio
async def test_execute_with_error(workspace: WorkspaceManager):
    """Script with error returns non-zero exit."""
    script = "raise ValueError('test error')"
    script_path = await workspace.save_script(script, prefix="error")

    executor = ScriptExecutor(workspace)
    result = await executor.execute(script_path)

    assert result.exit_code != 0
    assert "ValueError" in result.stderr or "ValueError" in result.output


@pytest.mark.asyncio
async def test_execute_timeout(workspace: WorkspaceManager):
    """Long-running script times out."""
    script = """
import time
time.sleep(10)
print('Should not see this')
"""
    script_path = await workspace.save_script(script, prefix="timeout")

    executor = ScriptExecutor(workspace)
    result = await executor.execute(script_path, timeout=1.0)

    assert result.timed_out
    assert "timed out" in result.output.lower()


@pytest.mark.asyncio
async def test_execute_path_validation(workspace: WorkspaceManager):
    """Executor rejects paths outside workspace."""
    unsafe_path = workspace.root.parent / "unsafe.py"
    unsafe_path.write_text("print('should not run')")

    executor = ScriptExecutor(workspace)

    with pytest.raises(ValueError, match="outside workspace"):
        await executor.execute(unsafe_path)


@pytest.mark.asyncio
async def test_execute_missing_file(workspace: WorkspaceManager):
    """Executor rejects missing files."""
    missing_path = workspace.scripts_dir / "nonexistent.py"

    executor = ScriptExecutor(workspace)

    with pytest.raises(FileNotFoundError):
        await executor.execute(missing_path)


@pytest.mark.asyncio
async def test_execute_multiline_output(workspace: WorkspaceManager):
    """Script with multiple print statements."""
    script = """
for i in range(5):
    print(f"Line {i}")
"""
    script_path = await workspace.save_script(script, prefix="multiline")

    executor = ScriptExecutor(workspace)
    result = await executor.execute(script_path)

    assert result.exit_code == 0
    assert "Line 0" in result.output
    assert "Line 4" in result.output
