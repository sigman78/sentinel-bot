"""Basic sandbox validation (Phase 6 - minimal)."""

from pathlib import Path

from sentinel.core.logging import get_logger

logger = get_logger("workspace.sandbox")


class SandboxValidator:
    """Basic script validation."""

    # Dangerous imports to block
    BLOCKED_IMPORTS = {
        "os.system",
        "subprocess",
        "eval",
        "exec",
        "__import__",
    }

    def validate_script(self, script_path: Path) -> tuple[bool, str | None]:
        """
        Basic validation - string matching for obvious issues.

        Returns: (is_safe, error_message)

        Note: This is basic validation. Phase 7 will add:
        - AST parsing for comprehensive analysis
        - RestrictedPython library
        - Container-based isolation (Docker)
        """
        try:
            content = script_path.read_text(encoding="utf-8")

            # Simple string matching for blocked patterns
            for blocked in self.BLOCKED_IMPORTS:
                if blocked in content:
                    return False, f"Script contains blocked operation: {blocked}"

            # Check for file operations outside workspace
            # (This is a simple check - full sandboxing needs more)
            dangerous_patterns = ["open(", "Path(", "os."]
            for pattern in dangerous_patterns:
                if pattern in content:
                    logger.warning(f"Script contains file operation: {pattern}")
                    # For Phase 6, we log but don't block
                    # Phase 7 will implement stricter validation

            return True, None

        except Exception as e:
            return False, f"Validation error: {str(e)}"
