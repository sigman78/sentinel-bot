"""
CLI entry point.

Commands:
- run: Start Telegram bot
- chat: Interactive CLI chat mode
- init: Initialize data directory
- health: Check LLM provider connectivity
"""

import asyncio
import sys
from datetime import datetime
from uuid import uuid4

from sentinel.core.config import Settings, get_settings
from sentinel.core.logging import get_logger, setup_logging
from sentinel.core.types import ContentType, Message


def main() -> int:
    """Main entry point."""
    settings = get_settings()
    setup_logging(log_file=settings.data_dir / "sentinel.log")
    logger = get_logger("cli")

    if len(sys.argv) < 2:
        print("Usage: sentinel <command>")
        print("Commands: run, chat, init, health")
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
    try:
        await interface.start()
        print("Telegram bot running. Press Ctrl+C to stop.")
        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
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

    print("Sentinel CLI Chat")
    print("Commands: /clear, /status, /exit")
    print("-" * 40)

    # Initialize components
    memory = SQLiteMemoryStore(settings.db_path)
    await memory.connect()

    router = create_default_router()
    if not router._providers:
        print("Error: No LLM providers available. Set SENTINEL_ANTHROPIC_API_KEY.")
        await memory.close()
        return 1

    llm = list(router._providers.values())[0]
    agent = DialogAgent(llm=llm, memory=memory)
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
        pass
    finally:
        await memory.close()

    print("\nGoodbye!")
    return 0


async def _health_check(settings: Settings) -> int:
    """Check LLM provider health."""
    from sentinel.llm.router import create_default_router

    print("Checking LLM providers...")
    router = create_default_router()

    if not router._providers:
        print("No providers configured.")
        return 1

    results = await router.health_check_all()
    for provider, healthy in results.items():
        status = "OK" if healthy else "FAILED"
        print(f"  {provider.value}: {status}")

    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
