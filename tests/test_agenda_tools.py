"""Tests for agenda management tools."""


import pytest

from sentinel.tools.builtin.agenda import (
    _parse_agenda,
    _rebuild_agenda,
    check_agenda,
    set_data_dir,
    update_agenda,
)


@pytest.fixture
def temp_agenda(tmp_path):
    """Create a temporary agenda file."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    agenda_path = data_dir / "agenda.md"
    agenda_content = """# Project agenda
This document used to track long and short term plans, priorities, context

## Current tasks and goals
- Task 1
- Task 2

## Active plans
Working on feature X

## Future plans
Plan to implement Y

## Preferences and experience
(Filled by agent on a go)

## Work notes
Note about Z
"""
    agenda_path.write_text(agenda_content, encoding="utf-8")
    set_data_dir(data_dir)
    return agenda_path


@pytest.mark.asyncio
async def test_check_agenda(temp_agenda):
    """Test reading agenda contents."""
    result = await check_agenda()

    assert result.success is True
    assert "content" in result.data
    assert "sections" in result.data
    assert "line_count" in result.data

    sections = result.data["sections"]
    assert "Current tasks and goals" in sections
    assert "Task 1" in sections["Current tasks and goals"]
    assert "Active plans" in sections
    assert "Work notes" in sections


@pytest.mark.asyncio
async def test_update_agenda_section(temp_agenda):
    """Test updating a specific section."""
    # Update a section
    result = await update_agenda(
        section="Current tasks and goals",
        content="- New task A\n- New task B"
    )

    assert result.success is True
    assert result.data["section"] == "Current tasks and goals"

    # Verify the update
    check_result = await check_agenda()
    sections = check_result.data["sections"]
    assert "New task A" in sections["Current tasks and goals"]
    assert "New task B" in sections["Current tasks and goals"]
    assert "Task 1" not in sections["Current tasks and goals"]


@pytest.mark.asyncio
async def test_update_agenda_preserves_structure(temp_agenda):
    """Test that updating preserves file structure."""
    # Update one section
    await update_agenda(
        section="Work notes",
        content="Updated note"
    )

    # Check that other sections are preserved
    check_result = await check_agenda()
    sections = check_result.data["sections"]

    assert "Work notes" in sections
    assert "Updated note" in sections["Work notes"]

    # Other sections should still exist
    assert "Current tasks and goals" in sections
    assert "Active plans" in sections
    assert "Future plans" in sections
    assert "Preferences and experience" in sections


@pytest.mark.asyncio
async def test_update_agenda_invalid_section(temp_agenda):
    """Test updating an invalid section."""
    result = await update_agenda(
        section="Invalid Section",
        content="Some content"
    )

    assert result.success is False
    assert "Unknown section" in result.error


@pytest.mark.asyncio
async def test_update_agenda_empty_section(temp_agenda):
    """Test clearing a section."""
    result = await update_agenda(
        section="Work notes",
        content=""
    )

    assert result.success is True

    # Verify the section is now empty (shows default text)
    check_result = await check_agenda()
    content = check_result.data["content"]

    # The section should exist with placeholder text
    assert "## Work notes" in content


def test_parse_agenda():
    """Test agenda content parsing."""
    content = """# Project agenda
This document used to track long and short term plans, priorities, context

## Current tasks and goals
- Task 1
- Task 2

## Active plans
Working on feature X

## Work notes
Note about Z
"""

    sections = _parse_agenda(content)

    assert "Current tasks and goals" in sections
    assert "- Task 1" in sections["Current tasks and goals"]
    assert "Active plans" in sections
    assert "Working on feature X" in sections["Active plans"]
    assert "Work notes" in sections


def test_rebuild_agenda():
    """Test rebuilding agenda from sections."""
    sections = {
        "Current tasks and goals": "- Task A\n- Task B",
        "Active plans": "Plan 1",
        "Future plans": "",
        "Preferences and experience": "Pref 1",
        "Work notes": "Note 1",
    }

    content = _rebuild_agenda(sections)

    assert "# Project agenda" in content
    assert "## Current tasks and goals" in content
    assert "- Task A" in content
    assert "## Active plans" in content
    assert "Plan 1" in content
    assert "## Future plans" in content
    assert "## Work notes" in content

    # Empty sections should have placeholder
    lines = content.split("\n")
    future_idx = lines.index("## Future plans")
    assert lines[future_idx + 1] == "(Filled by agent on a go)"


def test_rebuild_agenda_preserves_order():
    """Test that sections are always in the correct order."""
    # Provide sections in wrong order
    sections = {
        "Work notes": "Note",
        "Current tasks and goals": "Tasks",
        "Active plans": "Plans",
        "Future plans": "Future",
        "Preferences and experience": "Prefs",
    }

    content = _rebuild_agenda(sections)
    lines = [line for line in content.split("\n") if line.startswith("## ")]

    expected_order = [
        "## Current tasks and goals",
        "## Active plans",
        "## Future plans",
        "## Preferences and experience",
        "## Work notes",
    ]

    assert lines == expected_order
