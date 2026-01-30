"""Tests for stripping tool markup from LLM responses."""

from sentinel.agents.dialog import _strip_tool_markup


def test_strip_tool_use_blocks():
    """Test removal of <tool_use> blocks."""
    text = """Let me search for that information.

<tool_use>
<tool_name>web_search</tool_name>
<parameters>
<url>https://example.com</url>
</parameters>
</tool_use>

I found the results."""

    result = _strip_tool_markup(text)

    assert "<tool_use>" not in result
    assert "</tool_use>" not in result
    assert "Let me search for that information." in result
    assert "I found the results." in result


def test_strip_tool_call_blocks():
    """Test removal of <tool_call> blocks."""
    text = """Here's what I'll do:

<tool_call>
<name>fetch_webpage</name>
<args>{"url": "https://example.com"}</args>
</tool_call>

Done!"""

    result = _strip_tool_markup(text)

    assert "<tool_call>" not in result
    assert "</tool_call>" not in result
    assert "Here's what I'll do:" in result
    assert "Done!" in result


def test_strip_function_calls_blocks():
    """Test removal of <function_calls> blocks."""
    text = """Calling the function now.

<function_calls>
<invoke name="test">
<parameter name="arg">value</parameter>
</invoke>
</function_calls>

All set!"""

    result = _strip_tool_markup(text)

    assert "<function_calls>" not in result
    assert "</function_calls>" not in result
    assert "Calling the function now." in result
    assert "All set!" in result


def test_strip_multiple_blocks():
    """Test removal of multiple tool blocks."""
    text = """First action:

<tool_use>
<tool_name>search</tool_name>
</tool_use>

Second action:

<tool_use>
<tool_name>fetch</tool_name>
</tool_use>

Complete!"""

    result = _strip_tool_markup(text)

    assert "<tool_use>" not in result
    assert "First action:" in result
    assert "Second action:" in result
    assert "Complete!" in result


def test_clean_excessive_whitespace():
    """Test that excessive whitespace is cleaned up after removal."""
    text = """Text before.

<tool_use>
<tool_name>test</tool_name>
</tool_use>


Text after."""

    result = _strip_tool_markup(text)

    # Should not have triple newlines
    assert "\n\n\n" not in result
    assert "Text before." in result
    assert "Text after." in result


def test_no_markup_unchanged():
    """Test that text without markup is unchanged."""
    text = "This is a normal response without any tool markup."

    result = _strip_tool_markup(text)

    assert result == text


def test_real_world_example():
    """Test with real-world example from user report."""
    text = """Based on the search results, I can see there's quite a bit of market volatility \
happening right now. Let me fetch the most interesting article - that Reuters global markets \
piece that mentions AI bubble fears and geopolitical tensions affecting markets.

<tool_use>
<tool_name>fetch_webpage</tool_name>
<parameters>
<tool_parameter name="url">https://www.reuters.com/markets/</tool_parameter>
</parameters>
</tool_use>

Here's what's happening in the markets today:"""

    result = _strip_tool_markup(text)

    assert "<tool_use>" not in result
    assert "<tool_name>" not in result
    assert "<parameters>" not in result
    assert "Based on the search results" in result
    assert "Here's what's happening" in result
