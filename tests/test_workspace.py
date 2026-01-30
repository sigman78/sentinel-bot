"""Fast workspace tests without venv creation."""

from pathlib import Path

import pytest

from sentinel.workspace.manager import WorkspaceManager
from sentinel.workspace.sandbox import SandboxValidator


@pytest.fixture
def workspace_no_venv(tmp_path: Path):
    """Create workspace without venv (fast)."""
    ws = WorkspaceManager(tmp_path / "workspace")
    # Create directories manually without calling initialize()
    ws.scripts_dir.mkdir(parents=True, exist_ok=True)
    ws.output_dir.mkdir(parents=True, exist_ok=True)
    ws.temp_dir.mkdir(parents=True, exist_ok=True)
    return ws


@pytest.mark.asyncio
async def test_workspace_directories(workspace_no_venv: WorkspaceManager):
    """Workspace directories are created."""
    assert workspace_no_venv.scripts_dir.exists()
    assert workspace_no_venv.output_dir.exists()
    assert workspace_no_venv.temp_dir.exists()


@pytest.mark.asyncio
async def test_save_script(workspace_no_venv: WorkspaceManager):
    """Script saving works."""
    content = "print('hello world')"
    script_path = await workspace_no_venv.save_script(content, prefix="test")

    assert script_path.exists()
    assert script_path.read_text() == content
    assert script_path.suffix == ".py"
    assert script_path.parent == workspace_no_venv.scripts_dir


@pytest.mark.asyncio
async def test_save_script_size_limit(workspace_no_venv: WorkspaceManager):
    """Large scripts are rejected."""
    content = "x = 1\n" * 100_000  # Exceeds 100KB limit

    with pytest.raises(ValueError, match="exceeds size limit"):
        await workspace_no_venv.save_script(content)


@pytest.mark.asyncio
async def test_save_output(workspace_no_venv: WorkspaceManager):
    """Output saving works."""
    output = "Result: 42\nSuccess!"
    output_path = await workspace_no_venv.save_output("test_script", output)

    assert output_path.exists()
    assert output_path.read_text() == output
    assert output_path.parent == workspace_no_venv.output_dir


@pytest.mark.asyncio
async def test_cleanup_temp(workspace_no_venv: WorkspaceManager):
    """Temp cleanup removes files."""
    temp_file = workspace_no_venv.temp_dir / "test.txt"
    temp_file.write_text("temporary")

    await workspace_no_venv.cleanup_temp()

    assert not temp_file.exists()
    assert workspace_no_venv.temp_dir.exists()  # Directory still exists


@pytest.mark.asyncio
async def test_path_safety_inside_workspace(workspace_no_venv: WorkspaceManager):
    """Paths inside workspace are safe."""
    safe_path = workspace_no_venv.scripts_dir / "test.py"

    assert workspace_no_venv.is_path_safe(safe_path)


@pytest.mark.asyncio
async def test_path_safety_outside_workspace(workspace_no_venv: WorkspaceManager):
    """Paths outside workspace are unsafe."""
    unsafe_path = workspace_no_venv.root.parent / "escape.py"

    assert not workspace_no_venv.is_path_safe(unsafe_path)


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
