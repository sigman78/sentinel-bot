"""
Telegram bot interface.

Primary human-AI communication channel using python-telegram-bot.
Single-user mode: only responds to configured owner.
"""

from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from sentinel.agents.dialog import DialogAgent
from sentinel.core.config import get_settings
from sentinel.core.logging import get_logger
from sentinel.core.types import ContentType, Message
from sentinel.interfaces.base import InboundMessage, Interface, OutboundMessage
from sentinel.llm.router import create_default_router
from sentinel.memory.store import SQLiteMemoryStore

logger = get_logger("interfaces.telegram")


class TelegramInterface(Interface):
    """Telegram bot interface."""

    def __init__(self):
        settings = get_settings()
        self.token = settings.telegram_token
        self.owner_id = settings.telegram_owner_id
        self.app: Application | None = None
        self.agent: DialogAgent | None = None
        self.memory: SQLiteMemoryStore | None = None

    async def _init_components(self) -> None:
        """Initialize agent and memory store."""
        settings = get_settings()

        # Initialize memory
        self.memory = SQLiteMemoryStore(settings.db_path)
        await self.memory.connect()

        # Initialize LLM router
        router = create_default_router()
        claude = router.get(router._fallback_order[0])
        if not claude:
            raise RuntimeError("No LLM provider available")

        # Initialize dialog agent
        self.agent = DialogAgent(llm=claude, memory=self.memory)
        await self.agent.initialize()

        logger.info("Components initialized")

    async def start(self) -> None:
        """Start Telegram bot."""
        if not self.token:
            raise RuntimeError("SENTINEL_TELEGRAM_TOKEN not configured")
        if not self.owner_id:
            raise RuntimeError("SENTINEL_TELEGRAM_OWNER_ID not configured")

        await self._init_components()

        self.app = Application.builder().token(self.token).build()

        # Register handlers
        self.app.add_handler(CommandHandler("start", self._handle_start))
        self.app.add_handler(CommandHandler("status", self._handle_status))
        self.app.add_handler(CommandHandler("clear", self._handle_clear))
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )

        logger.info(f"Starting Telegram bot for owner {self.owner_id}")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    async def stop(self) -> None:
        """Stop Telegram bot."""
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
        if self.memory:
            await self.memory.close()
        logger.info("Telegram bot stopped")

    async def receive(self) -> InboundMessage:
        """Not used - telegram uses callback handlers."""
        raise NotImplementedError("Telegram uses callback-based message handling")

    async def send(self, message: OutboundMessage) -> None:
        """Send message to owner."""
        if self.app and self.owner_id:
            await self.app.bot.send_message(
                chat_id=self.owner_id,
                text=message.content,
                parse_mode="Markdown" if message.format == "markdown" else None,
            )

    def _is_owner(self, user_id: int) -> bool:
        """Check if message is from owner."""
        return user_id == self.owner_id

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not update.effective_user or not self._is_owner(update.effective_user.id):
            return

        await update.message.reply_text(
            "Sentinel initialized. How can I help you today?"
        )

    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        if not update.effective_user or not self._is_owner(update.effective_user.id):
            return

        status_lines = [
            "**Sentinel Status**",
            f"- Agent: {'Active' if self.agent else 'Not initialized'}",
            f"- Memory: {'Connected' if self.memory else 'Disconnected'}",
            f"- Conversation length: {len(self.agent.context.conversation) if self.agent else 0}",
        ]
        await update.message.reply_text("\n".join(status_lines), parse_mode="Markdown")

    async def _handle_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /clear command - reset conversation."""
        if not update.effective_user or not self._is_owner(update.effective_user.id):
            return

        if self.agent:
            self.agent.context.conversation.clear()
            await update.message.reply_text("Conversation cleared.")

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming text messages."""
        if not update.effective_user or not self._is_owner(update.effective_user.id):
            logger.debug(f"Ignoring message from non-owner: {update.effective_user.id}")
            return

        if not update.message or not update.message.text:
            return

        if not self.agent:
            await update.message.reply_text("Agent not initialized. Please restart.")
            return

        # Convert to internal message format
        message = Message(
            id=str(update.message.message_id),
            timestamp=datetime.now(),
            role="user",
            content=update.message.text,
            content_type=ContentType.TEXT,
            metadata={"telegram_user_id": update.effective_user.id},
        )

        try:
            # Show typing indicator
            await update.message.chat.send_action("typing")

            # Process message
            response = await self.agent.process(message)

            # Send response
            await update.message.reply_text(
                response.content,
                parse_mode="Markdown",
            )

            # Log cost if significant
            cost = response.metadata.get("cost_usd", 0)
            if cost > 0.01:
                logger.info(f"Response cost: ${cost:.4f}")

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await update.message.reply_text(
                f"Sorry, I encountered an error: {str(e)[:100]}"
            )
