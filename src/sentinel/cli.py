"""
CLI entry point.

Commands:
- run: Start the bot
- chat: Interactive CLI chat mode
- init: Initialize data directory
"""

import asyncio
import sys

from sentinel.core.config import get_settings
from sentinel.core.logging import get_logger, setup_logging


def main() -> int:
    """Main entry point."""
    settings = get_settings()
    setup_logging(log_file=settings.data_dir / "sentinel.log")
    logger = get_logger("cli")

    if len(sys.argv) < 2:
        print("Usage: sentinel <command>")
        print("Commands: run, chat, init")
        return 1

    command = sys.argv[1]

    if command == "init":
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized data directory: {settings.data_dir}")
        print(f"Created: {settings.data_dir}")
        return 0

    if command == "chat":
        logger.info("Starting CLI chat mode")
        asyncio.run(_chat_loop(settings))
        return 0

    if command == "run":
        logger.info("Starting Telegram bot")
        print("Telegram bot not implemented yet")
        return 1

    print(f"Unknown command: {command}")
    return 1


async def _chat_loop(settings) -> None:
    """Simple CLI chat for testing."""
    print("Sentinel CLI Chat (type 'exit' to quit)")
    print("-" * 40)

    while True:
        try:
            user_input = input("> ").strip()
            if user_input.lower() in ("exit", "quit", "q"):
                break
            if not user_input:
                continue

            # Placeholder - will integrate with dialog agent
            print(f"[Echo]: {user_input}")

        except (KeyboardInterrupt, EOFError):
            break

    print("\nGoodbye!")


if __name__ == "__main__":
    sys.exit(main())
