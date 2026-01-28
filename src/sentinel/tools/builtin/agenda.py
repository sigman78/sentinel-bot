"""Agenda management tools."""

import re
from pathlib import Path

from sentinel.core.types import ActionResult
from sentinel.tools.base import tool
from sentinel.tools.registry import register_tool

# Global reference to data directory (set during initialization)
_data_dir: Path | None = None


def set_data_dir(data_dir: Path) -> None:
    """Set the data directory path for tools to use."""
    global _data_dir
    _data_dir = data_dir


def _get_agenda_path() -> Path:
    """Get agenda file path or raise error."""
    if _data_dir is None:
        raise RuntimeError("Data directory not initialized. Call set_data_dir() first.")
    return _data_dir / "agenda.md"


def _parse_agenda(content: str) -> dict[str, str]:
    """Parse agenda content into sections."""
    sections = {}
    current_section = None
    section_lines = []

    for line in content.split("\n"):
        # Check for section headers (## Section Name)
        if line.startswith("## "):
            # Save previous section
            if current_section:
                sections[current_section] = "\n".join(section_lines).strip()
            # Start new section
            current_section = line[3:].strip()
            section_lines = []
        elif current_section:
            section_lines.append(line)

    # Save last section
    if current_section:
        sections[current_section] = "\n".join(section_lines).strip()

    return sections


def _rebuild_agenda(sections: dict[str, str]) -> str:
    """Rebuild agenda content from sections, preserving structure."""
    lines = ["# Project agenda", "This document used to track long and short term plans, priorities, context", ""]

    # Expected section order
    section_order = [
        "Current tasks and goals",
        "Active plans",
        "Future plans",
        "Preferences and experience",
        "Work notes",
    ]

    for section_name in section_order:
        lines.append(f"## {section_name}")
        if section_name in sections and sections[section_name]:
            lines.append(sections[section_name])
        else:
            lines.append("(Filled by agent on a go)")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


@tool(
    "check_agenda",
    "Read the current agenda to understand tasks, plans, and notes",
    examples=['check_agenda()'],
)
async def check_agenda() -> ActionResult:
    """
    Read the agenda file contents.

    Returns:
        ActionResult with agenda content
    """
    try:
        agenda_path = _get_agenda_path()
        if not agenda_path.exists():
            return ActionResult(
                success=False,
                error="Agenda file does not exist",
            )

        content = agenda_path.read_text(encoding="utf-8")
        sections = _parse_agenda(content)

        return ActionResult(
            success=True,
            data={
                "content": content,
                "sections": sections,
                "line_count": len(content.split("\n")),
            },
        )
    except Exception as e:
        return ActionResult(
            success=False,
            error=f"Failed to read agenda: {e}",
        )


@tool(
    "update_agenda",
    "Update specific sections of the agenda or append notes",
    examples=[
        'update_agenda(section="Current tasks and goals", content="- Implement agenda tools\\n- Test integration")',
        'update_agenda(section="Work notes", content="Completed Phase 6.6 tool calling")',
    ],
)
async def update_agenda(section: str, content: str) -> ActionResult:
    """
    Update a specific section of the agenda.

    Args:
        section: Section name to update (e.g., "Current tasks and goals")
        content: New content for the section

    Returns:
        ActionResult indicating success or failure
    """
    try:
        agenda_path = _get_agenda_path()
        if not agenda_path.exists():
            return ActionResult(
                success=False,
                error="Agenda file does not exist",
            )

        # Read and parse current content
        current_content = agenda_path.read_text(encoding="utf-8")
        sections = _parse_agenda(current_content)

        # Update the specified section
        if section not in sections:
            return ActionResult(
                success=False,
                error=f"Unknown section: {section}. Valid sections: {', '.join(sections.keys())}",
            )

        sections[section] = content.strip()

        # Rebuild and write
        new_content = _rebuild_agenda(sections)
        agenda_path.write_text(new_content, encoding="utf-8")

        return ActionResult(
            success=True,
            data={
                "section": section,
                "line_count": len(new_content.split("\n")),
                "message": f"Updated section: {section}",
            },
        )
    except Exception as e:
        return ActionResult(
            success=False,
            error=f"Failed to update agenda: {e}",
        )


def register_agenda_tools() -> None:
    """Register agenda management tools with the global registry."""
    register_tool(check_agenda._tool)  # type: ignore
    register_tool(update_agenda._tool)  # type: ignore
