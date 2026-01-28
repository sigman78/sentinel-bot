"""Tests for workspace management and execution."""

from pathlib import Path

import pytest

from sentinel.workspace.executor import ScriptExecutor
from sentinel.workspace.manager import WorkspaceManager
from sentinel.workspace.sandbox import SandboxValidator


@pytest.fixture
async def workspace(tmp_path: Path):
    """Create temporary workspace."""
    ws = WorkspaceManager(tmp_path / "workspace")
    await ws.initialize()
    return ws


@pytest.mark.asyncio
async def test_workspace_initialization(workspace: WorkspaceManager):
    """Workspace directories are created."""
    assert workspace.scripts_dir.exists()
    assert workspace.output_dir.exists()
    assert workspace.temp_dir.exists()


@pytest.mark.asyncio
async def test_workspace_venv_creation(workspace: WorkspaceManager):
    """Virtual environment is created."""
    assert workspace.venv_dir.exists()
    assert (workspace.venv_dir / "pyvenv.cfg").exists()


@pytest.mark.asyncio
async def test_save_script(workspace: WorkspaceManager):
    """Script saving works."""
    content = "print('hello world')"
    script_path = await workspace.save_script(content, prefix="test")

    assert script_path.exists()
    assert script_path.read_text() == content
    assert script_path.suffix == ".py"
    assert script_path.parent == workspace.scripts_dir


@pytest.mark.asyncio
async def test_save_script_size_limit(workspace: WorkspaceManager):
    """Large scripts are rejected."""
    content = "x = 1\n" * 100_000  # Exceeds 100KB limit

    with pytest.raises(ValueError, match="exceeds size limit"):
        await workspace.save_script(content)


@pytest.mark.asyncio
async def test_save_output(workspace: WorkspaceManager):
    """Output saving works."""
    output = "Result: 42\nSuccess!"
    output_path = await workspace.save_output("test_script", output)

    assert output_path.exists()
    assert output_path.read_text() == output
    assert output_path.parent == workspace.output_dir


@pytest.mark.asyncio
async def test_cleanup_temp(workspace: WorkspaceManager):
    """Temp cleanup removes files."""
    temp_file = workspace.temp_dir / "test.txt"
    temp_file.write_text("temporary")

    await workspace.cleanup_temp()

    assert not temp_file.exists()
    assert workspace.temp_dir.exists()  # Directory still exists


@pytest.mark.asyncio
async def test_get_python_path(workspace: WorkspaceManager):
    """Python path is correct."""
    python_path = workspace.get_python_path()

    assert python_path.exists()
    assert python_path.is_file()
    assert "python" in python_path.name.lower()


@pytest.mark.asyncio
async def test_path_safety_inside_workspace(workspace: WorkspaceManager):
    """Paths inside workspace are safe."""
    safe_path = workspace.scripts_dir / "test.py"

    assert workspace.is_path_safe(safe_path)


@pytest.mark.asyncio
async def test_path_safety_outside_workspace(workspace: WorkspaceManager):
    """Paths outside workspace are unsafe."""
    unsafe_path = workspace.root.parent / "escape.py"

    assert not workspace.is_path_safe(unsafe_path)


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


def test_sandbox_validator_safe_script(tmp_path: Path):
    """Validator approves safe scripts."""
    script = tmp_path / "safe.py"
    script.write_text("print('hello')\nx = 1 + 1\nprint(x)")

    validator = SandboxValidator()
    is_safe, error = validator.validate_script(script)

    assert is_safe
    assert error is None


def test_sandbox_validator_blocked_import(tmp_path: Path):
    """Validator blocks dangerous imports."""
    script = tmp_path / "dangerous.py"
    script.write_text("import os\nos.system('ls')")

    validator = SandboxValidator()
    is_safe, error = validator.validate_script(script)

    assert not is_safe
    assert "os.system" in error


def test_sandbox_validator_eval(tmp_path: Path):
    """Validator blocks eval."""
    script = tmp_path / "eval.py"
    script.write_text("result = eval('1 + 1')")

    validator = SandboxValidator()
    is_safe, error = validator.validate_script(script)

    assert not is_safe
    assert "eval" in error


def test_sandbox_validator_subprocess(tmp_path: Path):
    """Validator blocks subprocess."""
    script = tmp_path / "subprocess.py"
    script.write_text("import subprocess\nsubprocess.run(['ls'])")

    validator = SandboxValidator()
    is_safe, error = validator.validate_script(script)

    assert not is_safe
    assert "subprocess" in error
