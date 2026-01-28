"""Tests for tool framework."""

import pytest

from sentinel.core.types import ActionResult
from sentinel.tools.base import Tool, ToolParameter, tool
from sentinel.tools.executor import ToolExecutor
from sentinel.tools.parser import ToolParser
from sentinel.tools.registry import ToolRegistry


class TestToolParameter:
    """Test ToolParameter."""

    def test_create_parameter(self):
        param = ToolParameter(
            name="delay", type="string", description="Time delay", required=True
        )
        assert param.name == "delay"
        assert param.type == "string"
        assert param.required is True


class TestTool:
    """Test Tool class."""

    async def dummy_executor(self, arg1: str) -> ActionResult:
        return ActionResult(success=True, data={"arg1": arg1})

    def test_create_tool(self):
        tool_obj = Tool(
            name="test_tool",
            description="A test tool",
            parameters=[
                ToolParameter("arg1", "string", "First argument", required=True)
            ],
            executor=self.dummy_executor,
        )
        assert tool_obj.name == "test_tool"
        assert len(tool_obj.parameters) == 1

    def test_to_context_string(self):
        tool_obj = Tool(
            name="test_tool",
            description="A test tool",
            parameters=[
                ToolParameter("arg1", "string", "First argument", required=True),
                ToolParameter("arg2", "number", "Second argument", required=False, default=10),
            ],
            executor=self.dummy_executor,
            examples=["test_tool(arg1='hello')"],
        )
        context = tool_obj.to_context_string()
        assert "test_tool(" in context
        assert "arg1: string" in context
        assert "arg2: number (optional)" in context
        assert "First argument" in context
        assert "default: 10" in context
        assert "test_tool(arg1='hello')" in context

    def test_validate_args_success(self):
        tool_obj = Tool(
            name="test_tool",
            description="A test tool",
            parameters=[
                ToolParameter("arg1", "string", "First argument", required=True)
            ],
            executor=self.dummy_executor,
        )
        valid, error = tool_obj.validate_args({"arg1": "value"})
        assert valid is True
        assert error is None

    def test_validate_args_missing_required(self):
        tool_obj = Tool(
            name="test_tool",
            description="A test tool",
            parameters=[
                ToolParameter("arg1", "string", "First argument", required=True)
            ],
            executor=self.dummy_executor,
        )
        valid, error = tool_obj.validate_args({})
        assert valid is False
        assert "Missing required parameters" in error

    def test_validate_args_unknown_param(self):
        tool_obj = Tool(
            name="test_tool",
            description="A test tool",
            parameters=[
                ToolParameter("arg1", "string", "First argument", required=True)
            ],
            executor=self.dummy_executor,
        )
        valid, error = tool_obj.validate_args({"arg1": "value", "unknown": "bad"})
        assert valid is False
        assert "Unknown parameters" in error


class TestToolDecorator:
    """Test @tool decorator."""

    def test_basic_decorator(self):
        @tool("test_func", "Test function")
        async def test_func(arg1: str, arg2: int = 10) -> ActionResult:
            """
            A test function.

            arg1: First argument
            arg2: Second argument
            """
            return ActionResult(success=True)

        assert hasattr(test_func, "_tool")
        tool_obj = test_func._tool
        assert tool_obj.name == "test_func"
        assert tool_obj.description == "Test function"
        assert len(tool_obj.parameters) == 2
        assert tool_obj.parameters[0].name == "arg1"
        assert tool_obj.parameters[0].type == "string"
        assert tool_obj.parameters[0].required is True
        assert tool_obj.parameters[1].name == "arg2"
        assert tool_obj.parameters[1].type == "number"
        assert tool_obj.parameters[1].required is False
        assert tool_obj.parameters[1].default == 10


class TestToolRegistry:
    """Test ToolRegistry."""

    async def dummy_executor(self) -> ActionResult:
        return ActionResult(success=True)

    def test_register_and_get(self):
        registry = ToolRegistry()
        tool_obj = Tool(
            name="test_tool",
            description="Test",
            parameters=[],
            executor=self.dummy_executor,
        )
        registry.register(tool_obj)
        retrieved = registry.get("test_tool")
        assert retrieved is not None
        assert retrieved.name == "test_tool"

    def test_get_nonexistent(self):
        registry = ToolRegistry()
        retrieved = registry.get("nonexistent")
        assert retrieved is None

    def test_get_all(self):
        registry = ToolRegistry()
        tool1 = Tool("tool1", "Test 1", [], self.dummy_executor)
        tool2 = Tool("tool2", "Test 2", [], self.dummy_executor)
        registry.register(tool1)
        registry.register(tool2)
        all_tools = registry.get_all()
        assert len(all_tools) == 2
        names = {t.name for t in all_tools}
        assert names == {"tool1", "tool2"}

    def test_get_context_string(self):
        registry = ToolRegistry()
        tool_obj = Tool("test_tool", "A test tool", [], self.dummy_executor)
        registry.register(tool_obj)
        context = registry.get_context_string()
        assert "AVAILABLE TOOLS" in context
        assert "test_tool" in context
        assert "TOOL USAGE" in context


class TestToolParser:
    """Test ToolParser."""

    def test_parse_json_block(self):
        text = '''
Here's how to do it:

```json
{
    "tool": "add_reminder",
    "args": {
        "delay": "5m",
        "message": "test"
    }
}
```

That should work!
'''
        calls = ToolParser.extract_calls(text)
        assert len(calls) == 1
        assert calls[0].tool_name == "add_reminder"
        assert calls[0].arguments == {"delay": "5m", "message": "test"}

    def test_parse_code_block(self):
        text = '''
```
{
    "tool": "list_tasks",
    "args": {}
}
```
'''
        calls = ToolParser.extract_calls(text)
        assert len(calls) == 1
        assert calls[0].tool_name == "list_tasks"

    def test_parse_raw_json(self):
        text = '''
I'll use this tool: {"tool": "get_current_time", "args": {}}
'''
        calls = ToolParser.extract_calls(text)
        assert len(calls) == 1
        assert calls[0].tool_name == "get_current_time"

    def test_parse_multiple_calls(self):
        text = '''
```json
{"tool": "add_reminder", "args": {"delay": "5m", "message": "first"}}
```

And also:

```json
{"tool": "add_reminder", "args": {"delay": "10m", "message": "second"}}
```
'''
        calls = ToolParser.extract_calls(text)
        assert len(calls) == 2
        assert calls[0].arguments["message"] == "first"
        assert calls[1].arguments["message"] == "second"

    def test_parse_no_tool_calls(self):
        text = "Just a regular message with no tool calls."
        calls = ToolParser.extract_calls(text)
        assert len(calls) == 0

    def test_parse_invalid_json(self):
        text = '''
```json
{invalid json}
```
'''
        calls = ToolParser.extract_calls(text)
        assert len(calls) == 0


class TestToolExecutor:
    """Test ToolExecutor."""

    @pytest.mark.asyncio
    async def test_execute_success(self):
        async def test_tool_func(arg1: str) -> ActionResult:
            return ActionResult(success=True, data={"result": f"processed {arg1}"})

        registry = ToolRegistry()
        tool_obj = Tool(
            name="test_tool",
            description="Test",
            parameters=[ToolParameter("arg1", "string", "Arg 1", required=True)],
            executor=test_tool_func,
        )
        registry.register(tool_obj)

        executor = ToolExecutor(registry)
        from sentinel.tools.parser import ToolCall

        call = ToolCall(tool_name="test_tool", arguments={"arg1": "value"}, raw_json="")
        result = await executor.execute(call)

        assert result.success is True
        assert result.data["result"] == "processed value"

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self):
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        from sentinel.tools.parser import ToolCall

        call = ToolCall(tool_name="nonexistent", arguments={}, raw_json="")
        result = await executor.execute(call)

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_invalid_args(self):
        async def test_tool_func(arg1: str) -> ActionResult:
            return ActionResult(success=True)

        registry = ToolRegistry()
        tool_obj = Tool(
            name="test_tool",
            description="Test",
            parameters=[ToolParameter("arg1", "string", "Arg 1", required=True)],
            executor=test_tool_func,
        )
        registry.register(tool_obj)

        executor = ToolExecutor(registry)
        from sentinel.tools.parser import ToolCall

        # Missing required arg
        call = ToolCall(tool_name="test_tool", arguments={}, raw_json="")
        result = await executor.execute(call)

        assert result.success is False
        assert "Invalid arguments" in result.error

    @pytest.mark.asyncio
    async def test_execute_all(self):
        async def tool1() -> ActionResult:
            return ActionResult(success=True, data={"n": 1})

        async def tool2() -> ActionResult:
            return ActionResult(success=True, data={"n": 2})

        registry = ToolRegistry()
        registry.register(Tool("tool1", "Test 1", [], tool1))
        registry.register(Tool("tool2", "Test 2", [], tool2))

        executor = ToolExecutor(registry)
        from sentinel.tools.parser import ToolCall

        calls = [
            ToolCall("tool1", {}, ""),
            ToolCall("tool2", {}, ""),
        ]
        results = await executor.execute_all(calls)

        assert len(results) == 2
        assert results[0].success is True
        assert results[0].data["n"] == 1
        assert results[1].success is True
        assert results[1].data["n"] == 2
