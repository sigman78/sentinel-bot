"""File system agent - cross-platform CLI agent."""

import platform

from sentinel.agents.agentic_cli import AgenticCliConfig, CliTool, SafetyLimits

# Detect OS and provide appropriate tools
IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    # Windows-specific tools
    tools = [
        CliTool(
            name="dir",
            command="dir",
            help_text="""Display directory contents (Windows).

Common options:
  /B    Bare format (names only)
  /S    Include subdirectories
  /A    Show all files including hidden
  /O:N  Order by name
  /O:D  Order by date""",
            examples=[
                "dir",
                "dir /B",
                "dir /S *.py",
                "dir /A /O:D",
            ],
        ),
        CliTool(
            name="type",
            command="type",
            help_text="""Display file contents (Windows).

Usage: type [FILE]""",
            examples=[
                "type file.txt",
                "type README.md",
            ],
        ),
        CliTool(
            name="findstr",
            command="findstr",
            help_text="""Search for text patterns in files (Windows).

Usage: findstr [OPTIONS] PATTERN [FILE]...

Options:
  /I    Case-insensitive
  /N    Show line numbers
  /S    Search subdirectories
  /C:"text"  Literal string search""",
            examples=[
                'findstr "pattern" file.txt',
                'findstr /I /N "TODO" *.py',
                'findstr /S "error" *.log',
            ],
        ),
        CliTool(
            name="where",
            command="where",
            help_text="""Locate files (Windows).

Usage: where [/R dir] pattern

Options:
  /R dir    Search from directory recursively""",
            examples=[
                "where python",
                'where /R . *.py',
                'where /R src *.txt',
            ],
        ),
        CliTool(
            name="powershell",
            command="powershell",
            help_text="""Execute PowerShell commands (Windows).

Use for advanced file operations like:
  - Get-ChildItem (ls equivalent)
  - Select-String (grep equivalent)
  - Get-Content (cat equivalent)""",
            examples=[
                'powershell "Get-ChildItem -Recurse -Filter *.py"',
                'powershell "Get-Content README.md"',
                'powershell "Select-String -Pattern TODO -Path *.py"',
            ],
        ),
    ]
else:
    # Unix/Linux/macOS tools
    tools = [
        CliTool(
            name="ls",
            command="ls",
            help_text="""List directory contents.

Options:
  -l    Long format
  -a    Show hidden files
  -h    Human readable sizes
  -R    Recursive listing""",
            examples=[
                "ls",
                "ls -la",
                "ls -lh /path/to/dir",
            ],
        ),
        CliTool(
            name="cat",
            command="cat",
            help_text="""Display file contents.

Usage: cat [FILE]...""",
            examples=[
                "cat file.txt",
                "cat README.md",
            ],
        ),
        CliTool(
            name="head",
            command="head",
            help_text="""Output first part of files.

Options:
  -n NUM    Print first NUM lines (default 10)""",
            examples=[
                "head file.txt",
                "head -n 5 file.txt",
            ],
        ),
        CliTool(
            name="grep",
            command="grep",
            help_text="""Search for patterns in files.

Options:
  -i    Ignore case
  -n    Show line numbers
  -r    Recursive search""",
            examples=[
                "grep 'pattern' file.txt",
                "grep -i 'TODO' *.py",
                "grep -rn 'error' .",
            ],
        ),
        CliTool(
            name="find",
            command="find",
            help_text="""Search for files.

Usage: find [PATH] [OPTIONS]

Options:
  -name PATTERN    Find by name
  -type f          Files only
  -type d          Directories only""",
            examples=[
                "find . -name '*.py'",
                "find /path -type f -name '*.txt'",
            ],
        ),
    ]

config = AgenticCliConfig(
    name="FileAgent",
    description=f"I can explore and analyze files and directories using {'Windows' if IS_WINDOWS else 'Unix'} commands",
    tools=tools,
    limits=SafetyLimits(
        timeout_seconds=90,  # Longer to account for LLM latency
        max_iterations=10,   # Reduced - most tasks finish in 3-5 iterations
        max_consecutive_errors=3,
        max_total_errors=5,
    ),
)
