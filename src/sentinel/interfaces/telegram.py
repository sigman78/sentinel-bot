"""Telegram bot interface - single-user mode with persona support."""

from datetime import datetime

from telegram import Update
from telegram.constants import ParseMode
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
    """Telegram bot interface with persona from identity.md."""

    def __init__(self):
        settings = get_settings()
        self.token = settings.telegram_token
        self.owner_id = settings.telegram_owner_id
        self.app: Application | None = None
        self.agent: DialogAgent | None = None
        self.memory: SQLiteMemoryStore | None = None
        self._router = None

    async def _init_components(self) -> None:
        """Initialize agent and memory store."""
        settings = get_settings()

        self.memory = SQLiteMemoryStore(settings.db_path)
        await self.memory.connect()

        self._router = create_default_router()
        if not self._router.available_providers:
            raise RuntimeError("No LLM providers available")

        llm = list(self._router._providers.values())[0]
        self.agent = DialogAgent(llm=llm, memory=self.memory)
        await self.agent.initialize()

        logger.info(f"Initialized with identity: {settings.identity_path}")

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
        self.app.add_handler(CommandHandler("help", self._handle_help))
        self.app.add_handler(CommandHandler("status", self._handle_status))
        self.app.add_handler(CommandHandler("clear", self._handle_clear))
        self.app.add_handler(CommandHandler("agenda", self._handle_agenda))
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )

        logger.info(f"Starting Telegram bot for owner {self.owner_id}")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    async def stop(self) -> None:
        """Stop Telegram bot."""
        if self._router:
            await self._router.close_all()
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
        if self.memory:
            await self.memory.close()
        logger.info("Telegram bot stopped")

    async def receive(self) -> InboundMessage:
        raise NotImplementedError("Telegram uses callback-based message handling")

    async def send(self, message: OutboundMessage) -> None:
        """Send message to owner."""
        if self.app and self.owner_id:
            await self._safe_reply(
                self.owner_id, message.content, is_markdown=(message.format == "markdown")
            )

    def _is_owner(self, user_id: int) -> bool:
        return user_id == self.owner_id

    async def _safe_reply(
        self, chat_id: int, text: str, is_markdown: bool = True, reply_to: int | None = None
    ) -> None:
        """Send message with fallback if markdown fails."""
        try:
            if is_markdown:
                await self.app.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_to_message_id=reply_to,
                )
            else:
                await self.app.bot.send_message(
                    chat_id=chat_id, text=text, reply_to_message_id=reply_to
                )
        except Exception as e:
            # Fallback to plain text if markdown parsing fails
            logger.warning(f"Markdown failed, falling back to plain: {e}")
            await self.app.bot.send_message(
                chat_id=chat_id, text=text, reply_to_message_id=reply_to
            )

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not update.effective_user or not self._is_owner(update.effective_user.id):
            return

        # Extract name from identity if available
        name = "Sentinel"
        if self.agent and self.agent._identity:
            first_line = self.agent._identity.split("\n")[0]
            if "Senti" in first_line:
                name = "Senti"

        await update.message.reply_text(
            f"Hey! I'm {name}, ready to help. Send /help for commands."
        )

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        if not update.effective_user or not self._is_owner(update.effective_user.id):
            return

        help_text = """*Commands*
/start - Initialize bot
/status - Show agent status
/clear - Clear conversation history
/agenda - Show current agenda
/help - This message

Just send a message to chat with me."""

        await self._safe_reply(update.effective_chat.id, help_text)

    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        if not update.effective_user or not self._is_owner(update.effective_user.id):
            return

        providers = "none"
        if self._router:
            providers = ", ".join(p.value for p in self._router.available_providers)
        conv_len = len(self.agent.context.conversation) if self.agent else 0

        status = f"""*Status*
Agent: {'Active' if self.agent else 'Not initialized'}
Memory: {'Connected' if self.memory else 'Disconnected'}
Providers: {providers}
Conversation: {conv_len} messages"""

        await self._safe_reply(update.effective_chat.id, status)

    async def _handle_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /clear command."""
        if not update.effective_user or not self._is_owner(update.effective_user.id):
            return

        if self.agent:
            self.agent.context.conversation.clear()
            await update.message.reply_text("Conversation cleared.")

    async def _handle_agenda(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /agenda command - show current agenda."""
        if not update.effective_user or not self._is_owner(update.effective_user.id):
            return

        if self.agent and self.agent._agenda:
            # Truncate if too long for Telegram
            agenda = self.agent._agenda
            if len(agenda) > 4000:
                agenda = agenda[:4000] + "\n\n_(truncated)_"
            await self._safe_reply(update.effective_chat.id, agenda)
        else:
            await update.message.reply_text("No agenda set.")

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

        message = Message(
            id=str(update.message.message_id),
            timestamp=datetime.now(),
            role="user",
            content=update.message.text,
            content_type=ContentType.TEXT,
            metadata={"telegram_user_id": update.effective_user.id},
        )

        try:
            await update.message.chat.send_action("typing")
            response = await self.agent.process(message)

            await self._safe_reply(
                update.effective_chat.id,
                response.content,
                is_markdown=True,
                reply_to=update.message.message_id,
            )

            cost = response.metadata.get("cost_usd", 0)
            if cost > 0.01:
                logger.info(f"Response cost: ${cost:.4f}")

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            await update.message.reply_text(f"Error: {str(e)[:200]}")
