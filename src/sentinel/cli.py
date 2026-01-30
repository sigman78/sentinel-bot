"""
CLI entry point.

Commands:
- run: Start Telegram bot
- chat: Interactive CLI chat mode
- init: Initialize data directory
- health: Check LLM provider connectivity

Flags:
- --debug: Enable debug logging to file
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime
from uuid import uuid4

from sentinel.core.config import Settings, get_settings
from sentinel.core.logging import get_logger, setup_logging
from sentinel.core.types import ContentType, Message


def main() -> int:
    """Main entry point."""
    settings = get_settings()

    # Parse --debug flag (enables verbose DEBUG traces)
    debug_mode = "--debug" in sys.argv
    if debug_mode:
        sys.argv.remove("--debug")

    # Always log to file (INFO level includes warnings/errors)
    # --debug enables verbose DEBUG level
    log_level = logging.DEBUG if debug_mode else logging.INFO
    log_file = settings.data_dir / "sentinel.log"
    setup_logging(level=log_level, log_file=log_file)
    logger = get_logger("cli")

    logger.info(f"Logging to {log_file}" + (" (debug mode)" if debug_mode else ""))

    if len(sys.argv) < 2:
        print("Usage: sentinel [--debug] <command>")
        print("Commands: run, chat, init, health")
        print("Flags: --debug (enable debug logging to data/sentinel.log)")
        return 1

    command = sys.argv[1]

    if command == "init":
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized data directory: {settings.data_dir}")
        print(f"Created: {settings.data_dir}")
        return 0

    if command == "chat":
        logger.info("Starting CLI chat mode")
        return asyncio.run(_chat_loop(settings))

    if command == "run":
        logger.info("Starting Telegram bot")
        return asyncio.run(_run_telegram(settings))

    if command == "health":
        return asyncio.run(_health_check(settings))

    print(f"Unknown command: {command}")
    return 1


async def _run_telegram(settings: Settings) -> int:
    """Run Telegram bot."""
    from sentinel.interfaces.telegram import TelegramInterface

    interface = TelegramInterface()
    logger = get_logger("cli.telegram")

    # Set up signal handlers for graceful shutdown
    def handle_shutdown_signal(signum: int, frame: object | None) -> None:
        """Handle shutdown signals."""
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name}, initiating graceful shutdown")
        interface._shutdown_event.set()

    # Register signal handlers
    signal.signal(signal.SIGINT, handle_shutdown_signal)
    signal.signal(signal.SIGTERM, handle_shutdown_signal)

    try:
        await interface.start()
        print("Telegram bot running. Press Ctrl+C to stop or use /kill command.")

        # Keep running until shutdown signal received
        while not interface._shutdown_event.is_set():
            await asyncio.sleep(0.5)

        logger.info("Shutdown signal received, stopping bot")
        print("\nShutting down gracefully...")

    except Exception as e:
        logger.error(f"Error running bot: {e}", exc_info=True)
        print(f"Error: {e}")
        return 1
    finally:
        await interface.stop()
    return 0


async def _chat_loop(settings: Settings) -> int:
    """Interactive CLI chat with dialog agent."""
    from sentinel.agents.dialog import DialogAgent
    from sentinel.llm.router import create_default_router
    from sentinel.memory.store import SQLiteMemoryStore
    from sentinel.tools.builtin import register_all_builtin_tools
    from sentinel.tools.builtin.agenda import set_data_dir
    from sentinel.tools.builtin.web_search import set_brave_api_key
    from sentinel.tools.registry import get_global_registry

    print("Sentinel CLI Chat")
    print("Commands: /clear, /status, /exit")
    print("-" * 40)

    # Initialize components
    memory = SQLiteMemoryStore(settings.db_path)
    await memory.connect()

    router = create_default_router()
    if not router.available_providers:
        print("Error: No LLM providers available. Set SENTINEL_ANTHROPIC_API_KEY.")
        await memory.close()
        return 1

    # Register builtin tools
    register_all_builtin_tools()
    set_data_dir(settings.data_dir)
    set_brave_api_key(settings.brave_search_api_key)

    # Get tool registry for DialogAgent
    tool_registry = get_global_registry()

    agent = DialogAgent(llm=router, memory=memory, tool_registry=tool_registry)
    await agent.initialize()

    print("Ready.\n")

    try:
        while True:
            try:
                user_input = input("> ").strip()
            except EOFError:
                break

            if not user_input:
                continue

            # Handle commands
            if user_input.lower() in ("/exit", "exit", "quit", "q"):
                break
            if user_input == "/clear":
                agent.context.conversation.clear()
                print("Conversation cleared.\n")
                continue
            if user_input == "/status":
                print(f"Messages in context: {len(agent.context.conversation)}")
                print(f"Agent state: {agent.state.value}\n")
                continue

            # Process message
            message = Message(
                id=str(uuid4()),
                timestamp=datetime.now(),
                role="user",
                content=user_input,
                content_type=ContentType.TEXT,
            )

            try:
                response = await agent.process(message)
                cost = response.metadata.get("cost_usd", 0)
                print(f"\n{response.content}")
                if cost > 0:
                    print(f"  [{response.metadata.get('model', '?')} ${cost:.4f}]\n")
                else:
                    print()
            except Exception as e:
                print(f"Error: {e}\n")

    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        # Summarize session before closing if there's conversation history
        if agent and len(agent.context.conversation) >= 2:
            try:
                print("Saving conversation summary...")
                await agent.summarize_session()
            except Exception as e:
                print(f"Warning: Failed to save summary: {e}")

        await memory.close()

    print("Goodbye!")
    return 0


async def _health_check(settings: Settings) -> int:
    """Check LLM provider health."""
    from sentinel.llm.router import create_default_router

    print("Checking LLM providers...")
    router = create_default_router()

    if not router.available_providers:
        print("No providers configured.")
        return 1
    for provider in router.available_providers:
        print(f"  {provider}: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
