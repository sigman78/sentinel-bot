"""Integration tests for agentic CLI agents."""

from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from sentinel.agents.agentic_cli import AgenticCliAgent
from sentinel.core.types import ContentType, Message
from sentinel.llm.router import create_default_router
from sentinel.tools.decl.file_agent import config as file_agent_config


@pytest.mark.integration
async def test_file_agent_no_files_found():
    """Test FileAgent handles case when no matching files exist."""
    router = create_default_router()
    if not router.available_providers:
        pytest.skip("No LLM providers configured")

    llm = router

    # Create agent with current directory as working dir (root has no .py files)
    agent = AgenticCliAgent(config=file_agent_config, llm=llm, working_dir=str(Path.cwd()))

    # Test task: find Python files in current directory (should find none at root)
    message = Message(
        id=str(uuid4()),
        timestamp=datetime.now(),
        role="user",
        content="List all Python files in the current directory",
        content_type=ContentType.TEXT,
    )

    result = await agent.process(message)

    assert isinstance(result.content, str)
    assert len(result.content) > 0
    # Should mention no files or python
    assert (
        "no" in result.content.lower()
        or ".py" in result.content.lower()
        or "python" in result.content.lower()
    )
    print(f"\nNo files found result: {result.content}")


@pytest.mark.integration
async def test_file_agent_finds_files():
    """Test FileAgent successfully finds Python files when they exist."""
    router = create_default_router()
    if not router.available_providers:
        pytest.skip("No LLM providers configured")

    llm = router

    # Create agent with src directory as working dir (has .py files)
    src_dir = Path.cwd() / "src"
    if not src_dir.exists():
        pytest.skip("src directory not found")

    agent = AgenticCliAgent(config=file_agent_config, llm=llm, working_dir=str(src_dir))

    # Test task: find Python files in src directory
    message = Message(
        id=str(uuid4()),
        timestamp=datetime.now(),
        role="user",
        content="Find all Python files in the current directory and subdirectories",
        content_type=ContentType.TEXT,
    )

    result = await agent.process(message)

    assert isinstance(result.content, str)
    assert len(result.content) > 0
    # Should mention finding .py files or specific counts
    assert ".py" in result.content.lower() or "python" in result.content.lower()
    # Should NOT say "no files" or "not found"
    assert "no python" not in result.content.lower()
    print(f"\nFiles found result: {result.content}")


@pytest.mark.integration
async def test_file_agent_read_file():
    """Test FileAgent can read and analyze file contents."""
    router = create_default_router()
    if not router.available_providers:
        pytest.skip("No LLM providers configured")

    llm = router

    # Create a test file
    test_file = Path("test_temp_file.txt")
    test_content = "This is a test file with some content.\nLine 2 has important data.\n"
    test_file.write_text(test_content)

    try:
        agent = AgenticCliAgent(config=file_agent_config, llm=llm, working_dir=str(Path.cwd()))

        message = Message(
            id=str(uuid4()),
            timestamp=datetime.now(),
            role="user",
            content="Read the file test_temp_file.txt and tell me what's in it",
            content_type=ContentType.TEXT,
        )

        result = await agent.process(message)

        assert isinstance(result.content, str)
        # Should mention the file or its contents
        assert "test" in result.content.lower() or "content" in result.content.lower()
        print(f"\nRead file result: {result.content}")

    finally:
        # Cleanup
        if test_file.exists():
            test_file.unlink()


@pytest.mark.integration
async def test_file_agent_error_handling():
    """Test FileAgent handles errors gracefully."""
    router = create_default_router()
    if not router.available_providers:
        pytest.skip("No LLM providers configured")

    llm = router
    agent = AgenticCliAgent(config=file_agent_config, llm=llm, working_dir=str(Path.cwd()))

    # Try to read a non-existent file
    message = Message(
        id=str(uuid4()),
        timestamp=datetime.now(),
        role="user",
        content="Read the file nonexistent_file_xyz_123.txt",
        content_type=ContentType.TEXT,
    )

    result = await agent.process(message)

    assert isinstance(result.content, str)
    # Should either report error or determine task cannot be completed
    assert (
        "error" in result.content.lower()
        or "not found" in result.content.lower()
        or "cannot" in result.content.lower()
        or "does not exist" in result.content.lower()
    )
    print(f"\nError handling result: {result.content}")


@pytest.mark.integration
async def test_file_agent_safety_limits():
    """Test FileAgent enforces safety limits."""
    from sentinel.agents.agentic_cli import AgenticCliConfig, SafetyLimits

    router = create_default_router()
    if not router.available_providers:
        pytest.skip("No LLM providers configured")

    llm = router

    # Create config with very low limits
    strict_config = AgenticCliConfig(
        name="StrictFileAgent",
        description="File agent with strict limits",
        tools=file_agent_config.tools,
        limits=SafetyLimits(
            timeout_seconds=5,  # Very short timeout
            max_iterations=3,  # Very few iterations
            max_consecutive_errors=2,
            max_total_errors=3,
        ),
    )

    agent = AgenticCliAgent(config=strict_config, llm=llm, working_dir=str(Path.cwd()))

    # Complex task that might hit limits
    message = Message(
        id=str(uuid4()),
        timestamp=datetime.now(),
        role="user",
        content="Find all Python files recursively and count the total lines of code",
        content_type=ContentType.TEXT,
    )

    result = await agent.process(message)

    # Should complete or hit a safety limit
    assert isinstance(result.content, str)
    print(f"\nSafety limits result: {result.content}")

    # Check if it hit a limit (timeout, iterations, or completed)
    hit_limit = (
        "timeout" in result.content.lower()
        or "iterations" in result.content.lower()
        or "error" in result.content.lower()
        or result.metadata.get("status") == "success"
    )
    assert hit_limit
