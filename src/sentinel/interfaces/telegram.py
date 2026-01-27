"""Telegram bot interface - single-user mode with persona support."""

from datetime import datetime, timedelta

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from sentinel.agents.awareness import AwarenessAgent
from sentinel.agents.dialog import DialogAgent
from sentinel.agents.sleep import SleepAgent
from sentinel.core.config import get_settings
from sentinel.core.logging import get_logger
from sentinel.core.orchestrator import TaskPriority, get_orchestrator
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
        self._sleep_agent: SleepAgent | None = None
        self._awareness_agent: AwarenessAgent | None = None
        self._orchestrator = get_orchestrator()

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

        # Initialize background agents
        self._sleep_agent = SleepAgent(llm=llm, memory=self.memory)
        self._awareness_agent = AwarenessAgent(
            llm=llm,
            memory=self.memory,
            notify_callback=self._send_notification,
        )

        # Schedule background tasks
        self._orchestrator.schedule_task(
            task_id="sleep_consolidation",
            name="Memory consolidation",
            callback=self._run_sleep_cycle,
            interval=timedelta(hours=1),
            priority=TaskPriority.LOW,
            delay=timedelta(minutes=10),  # Wait 10min before first run
        )
        self._orchestrator.schedule_task(
            task_id="awareness_check",
            name="Awareness check",
            callback=self._run_awareness_check,
            interval=timedelta(minutes=1),
            priority=TaskPriority.NORMAL,
        )
        await self._orchestrator.start()

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
        """Stop Telegram bot, summarizing session first."""
        # Summarize conversation before shutdown
        if self.agent and len(self.agent.context.conversation) >= 2:
            try:
                await self.agent.summarize_session()
            except Exception as e:
                logger.warning(f"Failed to summarize on shutdown: {e}")

        await self._orchestrator.stop()
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

    async def _run_sleep_cycle(self) -> None:
        """Run sleep agent consolidation if system is idle."""
        if not self._orchestrator.is_idle():
            return
        if self._sleep_agent:
            result = await self._sleep_agent.run_consolidation()
            if result.get("facts_extracted", 0) > 0:
                logger.info(f"Sleep cycle: {result}")

    async def _run_awareness_check(self) -> None:
        """Run awareness agent checks."""
        if self._awareness_agent:
            await self._awareness_agent.check_all()

    async def _send_notification(self, message: str) -> None:
        """Send proactive notification to owner."""
        if self.app and self.owner_id:
            await self._safe_reply(self.owner_id, f"🔔 {message}", is_markdown=False)

    async def _safe_reply(
        self, chat_id: int, text: str, is_markdown: bool = True, reply_to: int | None = None
    ) -> None:
        """Send message with fallback if markdown fails, splits long messages."""
        # Telegram limit is 4096 chars, use 4000 for safety margin
        max_len = 4000
        chunks = self._split_message(text, max_len)

        for i, chunk in enumerate(chunks):
            # Only reply_to on first chunk
            reply_id = reply_to if i == 0 else None
            await self._send_chunk(chat_id, chunk, is_markdown, reply_id)

    async def _send_chunk(
        self, chat_id: int, text: str, is_markdown: bool, reply_to: int | None
    ) -> None:
        """Send a single message chunk with markdown fallback."""
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
            logger.warning(f"Markdown failed, falling back to plain: {e}")
            try:
                await self.app.bot.send_message(
                    chat_id=chat_id, text=text, reply_to_message_id=reply_to
                )
            except Exception as e2:
                logger.error(f"Failed to send message: {e2}", exc_info=True)

    def _split_message(self, text: str, max_len: int) -> list[str]:
        """Split message into chunks, preferring line breaks."""
        if len(text) <= max_len:
            return [text]

        chunks = []
        while text:
            if len(text) <= max_len:
                chunks.append(text)
                break

            # Find a good break point (newline or space)
            split_at = max_len
            newline_pos = text.rfind("\n", 0, max_len)
            if newline_pos > max_len // 2:
                split_at = newline_pos + 1
            else:
                space_pos = text.rfind(" ", 0, max_len)
                if space_pos > max_len // 2:
                    split_at = space_pos + 1

            chunks.append(text[:split_at])
            text = text[split_at:]

        return chunks

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
        """Handle /clear command - summarize then clear conversation."""
        if not update.effective_user or not self._is_owner(update.effective_user.id):
            return

        if self.agent:
            # Summarize before clearing if there's content
            if len(self.agent.context.conversation) >= 2:
                summary = await self.agent.summarize_session()
                if summary:
                    await update.message.reply_text(f"Session saved: {summary[:200]}")
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

        # Mark activity for background task scheduling
        self._orchestrator.mark_activity()

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
