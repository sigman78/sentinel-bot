"""Integration tests for CodeAgent with mocked LLM responses.

Tests the full workflow: task description → script generation → execution → result analysis.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from sentinel.agents.code import CodeAgent
from sentinel.core.types import ContentType, Message
from sentinel.llm.base import LLMResponse
from sentinel.llm.router import TaskType
from sentinel.memory.store import SQLiteMemoryStore
from sentinel.workspace.manager import WorkspaceManager


class MockLLM:
    """Mock LLM that returns predefined responses."""

    def __init__(self):
        self.responses = []
        self.call_count = 0

    def add_response(self, content: str, task: TaskType | None = None):
        """Add a response for the next LLM call."""
        self.responses.append((content, task))

    async def complete(self, messages, config, task=None):
        """Return next mocked response."""
        if self.call_count >= len(self.responses):
            raise ValueError("No more mocked responses available")

        content, expected_task = self.responses[self.call_count]
        self.call_count += 1

        return LLMResponse(
            content=content,
            model="mock-model",
            provider="mock",
            metadata={"cost_usd": 0.0},
        )

    async def close(self):
        """No-op close."""
        pass


@pytest.fixture
async def workspace(tmp_path):
    """Create temporary workspace for testing."""
    workspace_dir = tmp_path / "workspace"
    manager = WorkspaceManager(workspace_dir)
    await manager.initialize()
    yield manager
    # Cleanup handled by tmp_path fixture


@pytest.fixture
async def memory():
    """Create in-memory database for testing."""
    store = SQLiteMemoryStore(db_path=Path(":memory:"))
    await store.connect()
    yield store
    await store.close()


@pytest.fixture
async def code_agent(workspace, memory):
    """Create CodeAgent with mocked LLM."""
    llm = MockLLM()
    agent = CodeAgent(llm=llm, memory=memory, workspace_manager=workspace)
    await agent.initialize()
    return agent, llm


@pytest.mark.asyncio
@pytest.mark.integration
async def test_code_agent_successful_execution(code_agent):
    """Test successful code generation and execution."""
    agent, llm = code_agent

    # Mock responses: 1) script generation, 2) result analysis
    llm.add_response(
        content="""```python
# Calculate first 10 Fibonacci numbers
def fibonacci(n):
    fib = [0, 1]
    for i in range(2, n):
        fib.append(fib[i-1] + fib[i-2])
    return fib

result = fibonacci(10)
print("Fibonacci numbers:", result)
```""",
        task=TaskType.TOOL_CALL,
    )

    llm.add_response(
        content="Successfully calculated the first 10 Fibonacci numbers. The script ran without errors and produced the expected sequence: [0, 1, 1, 2, 3, 5, 8, 13, 21, 34].",
        task=TaskType.SUMMARIZATION,
    )

    # Create test message
    message = Message(
        id=str(uuid4()),
        timestamp=datetime.now(),
        role="user",
        content="Calculate the first 10 Fibonacci numbers",
        content_type=ContentType.TEXT,
    )

    # Process the task
    response = await agent.process(message)

    # Verify response
    assert response.role == "assistant"
    assert "Successfully calculated" in response.content
    assert "Fibonacci" in response.content
    assert llm.call_count == 2  # script generation + analysis

    # Verify memory was updated
    recent = await agent.memory.get_recent(limit=1)
    assert len(recent) == 1
    assert "Code execution" in recent[0].content
    assert recent[0].metadata is not None
    assert recent[0].metadata.get("exit_code") == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_code_agent_execution_error(code_agent):
    """Test code with runtime error."""
    agent, llm = code_agent

    # Mock responses: 1) buggy script, 2) error analysis
    llm.add_response(
        content="""```python
# This will cause a division by zero error
result = 10 / 0
print(result)
```""",
        task=TaskType.TOOL_CALL,
    )

    llm.add_response(
        content="The script failed with a division by zero error. Exit code 1 indicates the Python interpreter encountered an unhandled exception.",
        task=TaskType.SUMMARIZATION,
    )

    message = Message(
        id=str(uuid4()),
        timestamp=datetime.now(),
        role="user",
        content="Divide 10 by zero",
        content_type=ContentType.TEXT,
    )

    response = await agent.process(message)

    # Verify error was captured
    assert response.role == "assistant"
    assert "failed" in response.content.lower()
    assert llm.call_count == 2

    # Verify failed execution was logged in memory
    recent = await agent.memory.get_recent(limit=1)
    assert len(recent) == 1
    assert "failed" in recent[0].content.lower()
    assert recent[0].metadata is not None
    assert recent[0].metadata.get("exit_code") == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_code_agent_timeout(code_agent):
    """Test code that takes too long to execute."""
    agent, llm = code_agent

    # Mock responses: 1) slow script, 2) timeout analysis
    llm.add_response(
        content="""```python
import time
time.sleep(60)  # Will timeout before this completes
print("This won't be printed")
```""",
        task=TaskType.TOOL_CALL,
    )

    llm.add_response(
        content="The script execution timed out after exceeding the allowed duration. The operation was terminated to prevent hanging.",
        task=TaskType.SUMMARIZATION,
    )

    message = Message(
        id=str(uuid4()),
        timestamp=datetime.now(),
        role="user",
        content="Sleep for a minute",
        content_type=ContentType.TEXT,
    )

    # Override executor timeout for this test (script sleeps 60s, timeout is 2s)
    original_timeout = agent._executor._timeout_seconds
    agent._executor._timeout_seconds = 2.0

    try:
        response = await agent.process(message)

        # Verify timeout was detected
        assert response.role == "assistant"
        assert llm.call_count == 2

        # Check that execution record shows timeout
        recent = await agent.memory.get_recent(limit=1)
        assert len(recent) == 1

    finally:
        agent._executor._timeout_seconds = original_timeout


@pytest.mark.asyncio
@pytest.mark.integration
async def test_code_agent_multiple_tasks(code_agent):
    """Test processing multiple sequential code tasks."""
    agent, llm = code_agent

    tasks = [
        ("Calculate 5 factorial", "120"),
        ("Check if 17 is prime", "17 is prime"),
        ("Reverse the string 'hello'", "olleh"),
    ]

    for i, (task_desc, expected_output) in enumerate(tasks):
        # Mock script generation
        llm.add_response(
            content=f"""```python
# Task {i+1}: {task_desc}
print("{expected_output}")
```""",
            task=TaskType.TOOL_CALL,
        )

        # Mock analysis
        llm.add_response(
            content=f"Task completed successfully. Output: {expected_output}",
            task=TaskType.SUMMARIZATION,
        )

        message = Message(
            id=str(uuid4()),
            timestamp=datetime.now(),
            role="user",
            content=task_desc,
            content_type=ContentType.TEXT,
        )

        response = await agent.process(message)
        assert response.role == "assistant"
        assert "completed successfully" in response.content.lower()

    # Verify all tasks were logged
    assert llm.call_count == 6  # 3 tasks * 2 calls each
    recent = await agent.memory.get_recent(limit=3)
    assert len(recent) == 3


@pytest.mark.asyncio
@pytest.mark.integration
async def test_code_agent_script_extraction(code_agent):
    """Test extraction of code from various markdown formats."""
    agent, llm = code_agent

    # Test different code block formats
    code_formats = [
        "```python\nprint('format1')\n```",
        "```\nprint('format2')\n```",
        "print('format3')",  # No markdown blocks
    ]

    for i, code_format in enumerate(code_formats):
        llm.add_response(content=code_format, task=TaskType.TOOL_CALL)
        llm.add_response(
            content=f"Format {i+1} executed successfully",
            task=TaskType.SUMMARIZATION,
        )

        message = Message(
            id=str(uuid4()),
            timestamp=datetime.now(),
            role="user",
            content=f"Test format {i+1}",
            content_type=ContentType.TEXT,
        )

        response = await agent.process(message)
        assert response.role == "assistant"

    assert llm.call_count == 6  # 3 formats * 2 calls each


@pytest.mark.asyncio
@pytest.mark.integration
async def test_code_agent_exception_handling(code_agent):
    """Test that agent handles LLM exceptions gracefully."""
    agent, llm = code_agent

    # Don't add any mocked responses - this will cause an exception
    message = Message(
        id=str(uuid4()),
        timestamp=datetime.now(),
        role="user",
        content="This will fail",
        content_type=ContentType.TEXT,
    )

    response = await agent.process(message)

    # Verify error was handled
    assert response.role == "assistant"
    assert "failed" in response.content.lower()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_code_agent_output_persistence(code_agent):
    """Test that script output is persisted to workspace."""
    agent, llm = code_agent

    llm.add_response(
        content="""```python
print("Test output line 1")
print("Test output line 2")
print("Test output line 3")
```""",
        task=TaskType.TOOL_CALL,
    )

    llm.add_response(
        content="Script produced 3 lines of output",
        task=TaskType.SUMMARIZATION,
    )

    message = Message(
        id=str(uuid4())[:8],  # Use short ID for filename
        timestamp=datetime.now(),
        role="user",
        content="Print test output",
        content_type=ContentType.TEXT,
    )

    response = await agent.process(message)

    # Verify script was saved
    scripts = list(agent._workspace.scripts_dir.glob("*.py"))
    assert len(scripts) >= 1

    # Verify output was saved
    outputs = list(agent._workspace.output_dir.glob("*.txt"))
    assert len(outputs) >= 1

    # Read and verify output content
    output_content = outputs[0].read_text()
    assert "Test output line 1" in output_content
    assert "Test output line 2" in output_content
    assert "Test output line 3" in output_content
