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
from sentinel.agents.code import CodeAgent
from sentinel.agents.dialog import DialogAgent
from sentinel.agents.sleep import SleepAgent
from sentinel.core.config import get_settings
from sentinel.core.logging import get_logger
from sentinel.core.orchestrator import TaskPriority, get_orchestrator
from sentinel.core.types import ContentType, Message
from sentinel.interfaces.base import InboundMessage, Interface, OutboundMessage
from sentinel.llm.router import create_default_router
from sentinel.memory.store import SQLiteMemoryStore
from sentinel.tasks.manager import TaskManager

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
        self._code_agent: CodeAgent | None = None
        self._task_manager: TaskManager | None = None
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
        self._code_agent = CodeAgent(llm=llm, memory=self.memory)
        await self._code_agent.initialize()

        # Initialize task manager
        self._task_manager = TaskManager(
            memory=self.memory, notification_callback=self._send_notification
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
        self.app.add_handler(CommandHandler("code", self._handle_code))
        self.app.add_handler(CommandHandler("remind", self._handle_remind))
        self.app.add_handler(CommandHandler("schedule", self._handle_schedule))
        self.app.add_handler(CommandHandler("tasks", self._handle_tasks))
        self.app.add_handler(CommandHandler("cancel", self._handle_cancel))
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
        """Run awareness agent checks and task execution."""
        # Check awareness agent reminders/monitors
        if self._awareness_agent:
            await self._awareness_agent.check_all()

        # Check and execute due tasks
        if self._task_manager:
            results = await self._task_manager.check_and_execute_due_tasks()
            if results:
                logger.debug(f"Executed {len(results)} tasks")

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
/code <task> - Generate and execute Python code
/remind <time> <message> - Set one-time reminder (e.g., /remind 5m call mom)
/schedule <pattern> <task> - Schedule recurring task (e.g., /schedule daily 9am check news)
/tasks - List active scheduled tasks
/cancel <task_id> - Cancel a task
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

    async def _handle_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /code command - generate and execute Python code."""
        if not update.effective_user or not self._is_owner(update.effective_user.id):
            return

        if not self._code_agent:
            await update.message.reply_text("Code agent not initialized. Please restart.")
            return

        # Extract task from command arguments
        if not context.args:
            await update.message.reply_text(
                "Usage: /code <task description>\n"
                "Example: /code Calculate the first 20 Fibonacci numbers"
            )
            return

        task = " ".join(context.args)

        # Mark activity for background task scheduling
        self._orchestrator.mark_activity()

        try:
            await update.message.chat.send_action("typing")

            logger.info(f"CODE REQUEST: {task}")

            # Create message for code agent
            message = Message(
                id=str(update.message.message_id),
                timestamp=datetime.now(),
                role="user",
                content=task,
                content_type=ContentType.TEXT,
                metadata={"telegram_user_id": update.effective_user.id},
            )

            # Execute code task
            response = await self._code_agent.process(message)

            logger.info(f"CODE COMPLETE: {response.content[:100]}")

            # Send response
            await self._safe_reply(
                update.effective_chat.id,
                response.content,
                is_markdown=False,
                reply_to=update.message.message_id,
            )

        except Exception as e:
            logger.error(f"Error executing code: {e}", exc_info=True)
            await update.message.reply_text(f"Error: {str(e)[:200]}")

    async def _handle_remind(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /remind command - set one-time reminder."""
        if not update.effective_user or not self._is_owner(update.effective_user.id):
            return

        if not self._task_manager:
            await update.message.reply_text("Task manager not initialized.")
            return

        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "Usage: /remind <time> <message>\n"
                "Examples:\n"
                "  /remind 5m call mom\n"
                "  /remind 2h check oven\n"
                "  /remind 1d submit report"
            )
            return

        delay = context.args[0]
        message = " ".join(context.args[1:])

        result = await self._task_manager.add_reminder(delay, message)

        if result.success:
            trigger_at = result.data.get("trigger_at", "")
            await update.message.reply_text(
                f"Reminder set: {message}\nWill trigger at {trigger_at[:16]}"
            )
        else:
            await update.message.reply_text(f"Error: {result.error}")

    async def _handle_schedule(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /schedule command - schedule recurring reminder."""
        if not update.effective_user or not self._is_owner(update.effective_user.id):
            return

        if not self._task_manager:
            await update.message.reply_text("Task manager not initialized.")
            return

        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "Usage: /schedule <pattern> <task>\n"
                "Examples:\n"
                "  /schedule daily 9am check news\n"
                "  /schedule weekdays 6pm workout reminder\n"
                "  /schedule monday 10am weekly review"
            )
            return

        # Parse schedule pattern - could be "daily 9am" or "weekdays 6pm" etc
        # We need to find where the pattern ends and task description begins
        # For simplicity, assume pattern is first 1-2 args
        if len(context.args) >= 3 and context.args[1].replace(":", "").replace("am", "").replace("pm", "").replace(".", "").isdigit():
            # Pattern is 2 words: "daily 9am"
            schedule = f"{context.args[0]} {context.args[1]}"
            description = " ".join(context.args[2:])
        else:
            # Pattern is 1 word: this shouldn't happen with valid input
            await update.message.reply_text(
                "Invalid format. Use: /schedule <pattern> <time> <task>\n"
                "Example: /schedule daily 9am check news"
            )
            return

        from sentinel.tasks.types import TaskType

        result = await self._task_manager.add_recurring_task(
            schedule=schedule,
            task_type=TaskType.REMINDER,
            description=description,
        )

        if result.success:
            task_id = result.data.get("task_id", "")
            next_run = result.data.get("next_run", "")
            await update.message.reply_text(
                f"Scheduled task {task_id}: {description}\n"
                f"Next run: {next_run[:16]}"
            )
        else:
            await update.message.reply_text(f"Error: {result.error}")

    async def _handle_tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /tasks command - list active tasks."""
        if not update.effective_user or not self._is_owner(update.effective_user.id):
            return

        if not self._task_manager:
            await update.message.reply_text("Task manager not initialized.")
            return

        tasks = await self._task_manager.list_tasks()

        if not tasks:
            await update.message.reply_text("No active tasks.")
            return

        lines = ["*Active Tasks*\n"]
        for task in tasks:
            task_type = task["schedule_type"]
            lines.append(
                f"`{task['id']}` [{task_type}] {task['description']}\n"
                f"  Next: {task['next_run'][:16]}\n"
            )

        await self._safe_reply(update.effective_chat.id, "\n".join(lines))

    async def _handle_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /cancel command - cancel a task."""
        if not update.effective_user or not self._is_owner(update.effective_user.id):
            return

        if not self._task_manager:
            await update.message.reply_text("Task manager not initialized.")
            return

        if not context.args:
            await update.message.reply_text(
                "Usage: /cancel <task_id>\n" "Use /tasks to see task IDs."
            )
            return

        task_id = context.args[0]
        result = await self._task_manager.cancel_task(task_id)

        if result.success:
            await update.message.reply_text(f"Cancelled task {task_id}")
        else:
            await update.message.reply_text(f"Error: {result.error}")

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

        # Log incoming message
        logger.debug(f"USER: {update.message.text}")

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

            # Log outgoing response
            if len(response.content) > 200:
                logger.debug(f"BOT: {response.content[:200]}...")
            else:
                logger.debug(f"BOT: {response.content}")

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
