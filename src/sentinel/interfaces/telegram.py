"""Telegram bot interface - single-user mode with persona support."""

import asyncio
import base64
from datetime import datetime, timedelta
from io import BytesIO

from telegram import BotCommand, Update
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
from sentinel.llm.base import LLMProvider
from sentinel.llm.router import create_default_router
from sentinel.memory.store import SQLiteMemoryStore
from sentinel.tasks.manager import TaskManager
from sentinel.tools.builtin import register_all_builtin_tools
from sentinel.tools.builtin.agenda import set_data_dir
from sentinel.tools.builtin.tasks import set_task_manager
from sentinel.tools.registry import get_global_registry

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
        self._last_message_time: datetime | None = None
        self._shutdown_event = asyncio.Event()

    async def _init_components(self) -> None:
        """Initialize agent and memory store."""
        settings = get_settings()

        self.memory = SQLiteMemoryStore(settings.db_path)
        await self.memory.connect()

        self._router = create_default_router()
        if not self._router.available_providers:
            raise RuntimeError("No LLM providers available")

        # Initialize task manager first (needed by tools)
        self._task_manager = TaskManager(
            memory=self.memory, notification_callback=self._send_notification
        )

        # Register builtin tools
        register_all_builtin_tools()
        set_task_manager(self._task_manager)
        set_data_dir(settings.data_dir)

        # Get tool registry for DialogAgent
        tool_registry = get_global_registry()

        # Smart LLM assignment: cheap models for sub-agents, premium for DialogAgent
        cheap_llm = self._get_cheap_llm()
        premium_llm = self._get_premium_llm()

        logger.info(f"Sub-agents using: {cheap_llm.provider_type.value}")
        logger.info(f"DialogAgent using: {premium_llm.provider_type.value}")

        # Initialize all specialized agents (auto-discovered + hardcoded)
        from sentinel.core.agent_service import initialize_agents

        tool_agent_registry = initialize_agents(
            cheap_llm=cheap_llm,
            working_dir=settings.data_dir.parent,
        )

        self.agent = DialogAgent(
            llm=premium_llm,
            memory=self.memory,
            tool_registry=tool_registry,
            tool_agent_registry=tool_agent_registry,
        )
        await self.agent.initialize()

        # Initialize background agents with cheap LLM
        self._sleep_agent = SleepAgent(llm=cheap_llm, memory=self.memory)
        self._awareness_agent = AwarenessAgent(
            llm=cheap_llm,
            memory=self.memory,
            notify_callback=self._send_notification,
        )
        self._code_agent = CodeAgent(llm=cheap_llm, memory=self.memory)
        await self._code_agent.initialize()

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

    def _get_cheap_llm(self) -> LLMProvider:
        """Get cheapest available LLM provider for sub-agents.

        Priority: local > openrouter > claude
        """
        from sentinel.llm.base import ProviderType

        # Prefer local models (free/fast)
        if ProviderType.LOCAL in self._router.available_providers:
            return self._router.get(ProviderType.LOCAL)

        # Then OpenRouter (cheaper than direct Claude)
        if ProviderType.OPENROUTER in self._router.available_providers:
            return self._router.get(ProviderType.OPENROUTER)

        # Fallback to Claude if nothing else available
        if ProviderType.CLAUDE in self._router.available_providers:
            return self._router.get(ProviderType.CLAUDE)

        # Should never reach here due to check in _init_components
        raise RuntimeError("No LLM providers available")

    def _get_premium_llm(self) -> LLMProvider:
        """Get premium LLM provider for DialogAgent.

        Priority: claude > openrouter > local
        """
        from sentinel.llm.base import ProviderType

        # Prefer Claude for best conversational quality
        if ProviderType.CLAUDE in self._router.available_providers:
            return self._router.get(ProviderType.CLAUDE)

        # Fallback to OpenRouter
        if ProviderType.OPENROUTER in self._router.available_providers:
            return self._router.get(ProviderType.OPENROUTER)

        # Last resort: local model
        if ProviderType.LOCAL in self._router.available_providers:
            return self._router.get(ProviderType.LOCAL)

        # Should never reach here
        raise RuntimeError("No LLM providers available")

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
        self.app.add_handler(CommandHandler("memory", self._handle_memory))
        self.app.add_handler(CommandHandler("code", self._handle_code))
        self.app.add_handler(CommandHandler("remind", self._handle_remind))
        self.app.add_handler(CommandHandler("schedule", self._handle_schedule))
        self.app.add_handler(CommandHandler("tasks", self._handle_tasks))
        self.app.add_handler(CommandHandler("cancel", self._handle_cancel))
        self.app.add_handler(CommandHandler("ctx", self._handle_ctx))
        self.app.add_handler(CommandHandler("kill", self._handle_kill))
        self.app.add_handler(
            MessageHandler(filters.PHOTO, self._handle_photo)
        )
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )

        logger.info(f"Starting Telegram bot for owner {self.owner_id}")
        await self.app.initialize()
        await self.app.start()

        # Set up bot command menu
        await self._setup_bot_commands()

        await self.app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    async def stop(self) -> None:
        """Stop Telegram bot, summarizing session first."""
        logger.info("Stopping Telegram bot gracefully")

        # Summarize conversation before shutdown
        if self.agent and len(self.agent.context.conversation) >= 2:
            try:
                logger.info("Saving conversation summary")
                await self.agent.summarize_session()
                logger.info("Conversation summary saved")
            except Exception as e:
                logger.warning(f"Failed to summarize on shutdown: {e}")

        # Stop orchestrator and background agents
        logger.info("Stopping orchestrator and background agents")
        await self._orchestrator.stop()

        # Close LLM router connections
        if self._router:
            logger.info("Closing LLM router connections")
            await self._router.close_all()

        # Stop Telegram application
        if self.app:
            logger.info("Stopping Telegram application")
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()

        # Close memory store
        if self.memory:
            logger.info("Closing memory store")
            await self.memory.close()

        logger.info("Telegram bot stopped gracefully")

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

    def _should_quote_reply(self, message_time: datetime) -> bool:
        """Determine if we should quote-reply based on message timing.

        Only quote-replies when:
        - Replying to older messages (5+ minutes gap from last message)
        - This helps maintain context for out-of-order or delayed responses
        """
        if self._last_message_time is None:
            return False

        time_gap = (message_time - self._last_message_time).total_seconds()
        # Quote-reply if 5+ minutes since last message (returning to earlier context)
        return time_gap >= 300

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
/memory - Show memory system overview
/code <task> - Generate and execute Python code
/remind <time> <message> - Set one-time reminder (e.g., /remind 5m call mom)
/schedule <pattern> <task> - Schedule recurring task (e.g., /schedule daily 9am check news)
/tasks - List active scheduled tasks
/cancel <task_id> - Cancel a task
/ctx - Show debug context
/kill - Gracefully shutdown the bot
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

    async def _handle_memory(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /memory command - show memory system overview."""
        if not update.effective_user or not self._is_owner(update.effective_user.id):
            return

        if not self.memory:
            await update.message.reply_text("Memory not initialized.")
            return

        try:
            # Gather memory statistics
            from datetime import datetime, timedelta

            # 1. Get memory counts
            episodic_count = 0
            semantic_count = 0

            # Count episodic memories
            try:
                async with self.memory.conn.execute(
                    "SELECT COUNT(*) FROM episodes"
                ) as cursor:
                    row = await cursor.fetchone()
                    episodic_count = row[0] if row else 0
            except Exception:
                pass

            # Count semantic memories (facts)
            try:
                async with self.memory.conn.execute(
                    "SELECT COUNT(*) FROM facts WHERE superseded_by IS NULL"
                ) as cursor:
                    row = await cursor.fetchone()
                    semantic_count = row[0] if row else 0
            except Exception:
                pass

            # 2. Get recent memories (last 24 hours)
            recent_memories = []
            try:
                yesterday = datetime.now() - timedelta(days=1)
                async with self.memory.conn.execute(
                    "SELECT summary, timestamp FROM episodes WHERE timestamp > ? ORDER BY timestamp DESC LIMIT 5",
                    (yesterday,)
                ) as cursor:
                    async for row in cursor:
                        recent_memories.append({
                            "content": row[0],
                            "timestamp": row[1]
                        })
            except Exception:
                pass

            # 3. Get user profile
            profile_summary = "Not set"
            if hasattr(self.memory, "get_profile"):
                try:
                    profile = await self.memory.get_profile()
                    if profile:
                        profile_summary = f"{profile.name}"
                        if profile.timezone:
                            profile_summary += f" ({profile.timezone})"
                        if profile.interests:
                            profile_summary += f"\nInterests: {', '.join(profile.interests[:3])}"
                            if len(profile.interests) > 3:
                                profile_summary += f" +{len(profile.interests) - 3} more"
                        if profile.preferences:
                            pref_count = len(profile.preferences)
                            profile_summary += f"\nPreferences: {pref_count} set"
                except Exception:
                    pass

            # 4. Get agenda summary
            agenda_summary = "Empty"
            if self.agent and self.agent._agenda:
                lines = self.agent._agenda.split("\n")
                # Get first non-empty line as summary
                for line in lines:
                    if line.strip() and not line.startswith("#"):
                        agenda_summary = line.strip()[:100]
                        break
                if len(lines) > 5:
                    agenda_summary += f"\n({len(lines)} lines total)"

            # 5. Working memory (conversation)
            working_memory_size = 0
            if self.agent:
                working_memory_size = len(self.agent.context.conversation)

            # Build response
            report = f"""*Memory System Overview*

📊 *Memory Hierarchy*
• Working: {working_memory_size} messages (current session)
• Episodic: {episodic_count} memories (conversations)
• Semantic: {semantic_count} facts (knowledge)

👤 *User Profile*
{profile_summary}

📝 *Agenda*
{agenda_summary}

🕒 *Recent Activity* (last 24h)
"""

            if recent_memories:
                for mem in recent_memories[:3]:
                    # Format timestamp
                    ts = mem["timestamp"]
                    if isinstance(ts, str):
                        ts = datetime.fromisoformat(ts)
                    time_str = ts.strftime("%H:%M") if isinstance(ts, datetime) else "?"
                    # Truncate content
                    content = mem["content"][:80]
                    if len(mem["content"]) > 80:
                        content += "..."
                    report += f"• {time_str}: {content}\n"
            else:
                report += "• No recent memories\n"

            await self._safe_reply(update.effective_chat.id, report)

        except Exception as e:
            logger.error(f"Error in /memory command: {e}", exc_info=True)
            await update.message.reply_text(f"Error gathering memory stats: {str(e)[:100]}")

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

    async def _handle_ctx(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /ctx command - show raw dialog context for debugging."""
        if not update.effective_user or not self._is_owner(update.effective_user.id):
            return

        if not self.agent:
            await update.message.reply_text("Agent not initialized.")
            return

        # Build context dump
        conv_count = len(self.agent.context.conversation)
        conv_dump = []

        for i, msg in enumerate(self.agent.context.conversation[-10:], 1):  # Last 10 messages
            metadata_str = f" (meta: {msg.metadata})" if msg.metadata else ""
            conv_dump.append(
                f"{i}. [{msg.role}] {msg.content[:100]}{'...' if len(msg.content) > 100 else ''}{metadata_str}"
            )

        context_info = f"""*Context Debug*

Agent ID: `{self.agent.context.agent_id}`
Agent Type: `{self.agent.context.agent_type.value}`
Conversation Length: {conv_count} messages
Showing: Last {min(10, conv_count)} messages

*Recent Messages:*
```
{chr(10).join(conv_dump) if conv_dump else '(empty)'}
```

*Agent State:*
State: `{self.agent.state.value}`
Max History: {self.agent._max_history}
User Profile: {self.agent._user_profile.name}

*Memory Info:*
Identity Path: `{self.agent._identity_path}`
Agenda Path: `{self.agent._agenda_path}`
"""

        await self._safe_reply(update.effective_chat.id, context_info)

    async def _handle_kill(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /kill command - gracefully shutdown the bot."""
        if not update.effective_user or not self._is_owner(update.effective_user.id):
            return

        logger.info("Received /kill command, initiating graceful shutdown")
        await update.message.reply_text("Shutting down gracefully... Saving memories and disconnecting.")

        # Signal the shutdown event
        self._shutdown_event.set()

    async def _setup_bot_commands(self) -> None:
        """Set up bot command menu for Telegram."""
        commands = [
            BotCommand("start", "Initialize bot"),
            BotCommand("help", "Show available commands"),
            BotCommand("status", "Show bot status and info"),
            BotCommand("clear", "Clear conversation and save summary"),
            BotCommand("agenda", "Show current agenda"),
            BotCommand("memory", "Show memory system overview"),
            BotCommand("remind", "Set reminder (e.g. /remind 5m call mom)"),
            BotCommand("schedule", "Schedule recurring task"),
            BotCommand("tasks", "List scheduled tasks"),
            BotCommand("cancel", "Cancel task by ID"),
            BotCommand("code", "Execute code in workspace"),
            BotCommand("ctx", "Show debug context"),
            BotCommand("kill", "Gracefully shutdown the bot"),
        ]

        try:
            await self.app.bot.set_my_commands(commands)
            logger.info("Bot commands menu configured")
        except Exception as e:
            logger.warning(f"Failed to set bot commands: {e}")

    def _build_image_context_prompt(self) -> str:
        """Build context-aware prompt for images sent without caption.

        Analyzes recent conversation to understand why the image might have been sent
        and creates a natural prompt for the agent to react appropriately.
        """
        if not self.agent or not self.agent.context.conversation:
            # No conversation context - generic but natural
            return (
                "The user sent me an image. I should look at it and react naturally. "
                "Is this a meme, screenshot, photo, diagram, or something else? "
                "Does it seem to be related to something we discussed? "
                "I should respond in a conversational way - comment, ask questions, "
                "or relate it to our conversation rather than just describing it."
            )

        # Get recent conversation context (last 3 messages)
        recent = self.agent.context.conversation[-3:]
        has_recent_question = any(
            "?" in msg.content and msg.role == "user"
            for msg in recent
        )
        last_user_message = next(
            (msg.content for msg in reversed(recent) if msg.role == "user"),
            None
        )

        if has_recent_question and last_user_message:
            # Might be answering a recent question with an image
            return (
                f"The user just sent me an image. Looking at our recent conversation, "
                f"they asked: '{last_user_message[:100]}...'. "
                f"This image might be related to that question or topic. "
                f"I should analyze the image in that context and respond naturally. "
                f"Is this answering their question? Sharing an example? A meme response? "
                f"React appropriately based on what the image shows and our conversation."
            )
        elif last_user_message:
            # Recent conversation but no question
            return (
                f"The user sent me an image. We were just discussing: '{last_user_message[:100]}...'. "
                f"This might be related, or it could be a new topic. "
                f"I should look at the image and react naturally - is it funny? Interesting? "
                f"Does it relate to what we talked about? "
                f"Respond in a conversational way rather than just describing it."
            )
        else:
            # Conversation exists but no clear recent context
            return (
                "The user sent me an image. I should look at it and react like a human would. "
                "Is this a meme I should comment on? A screenshot they want help with? "
                "A photo they want to share? A diagram to analyze? "
                "React naturally and conversationally based on what I see."
            )

    async def _handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming photo messages with vision support."""
        if not update.effective_user or not self._is_owner(update.effective_user.id):
            logger.debug(f"Ignoring photo from non-owner: {update.effective_user.id}")
            return

        if not update.message or not update.message.photo:
            return

        if not self.agent:
            await update.message.reply_text("Agent not initialized. Please restart.")
            return

        # Mark activity for background task scheduling
        self._orchestrator.mark_activity()

        # Get the highest resolution photo
        photo = update.message.photo[-1]

        try:
            # Download photo
            photo_file = await context.bot.get_file(photo.file_id)
            photo_bytes = BytesIO()
            await photo_file.download_to_memory(photo_bytes)
            photo_bytes.seek(0)

            # Convert to base64
            image_data = base64.b64encode(photo_bytes.read()).decode('utf-8')

            # Build contextual prompt based on caption and conversation context
            if update.message.caption:
                # User provided explicit caption/question
                caption = update.message.caption
            else:
                # No caption - build context-aware prompt
                caption = self._build_image_context_prompt()

            logger.debug(f"USER: [Image] {caption}")

            message_time = datetime.now()
            message = Message(
                id=str(update.message.message_id),
                timestamp=message_time,
                role="user",
                content=caption,
                content_type=ContentType.IMAGE,
                metadata={
                    "telegram_user_id": update.effective_user.id,
                    "images": [{
                        "data": image_data,
                        "media_type": "image/jpeg",
                        "source": "telegram"
                    }]
                },
            )

            await update.message.chat.send_action("typing")
            response = await self.agent.process(message)

            # Log outgoing response
            if len(response.content) > 200:
                logger.debug(f"BOT: {response.content[:200]}...")
            else:
                logger.debug(f"BOT: {response.content}")

            # Reply to the image message
            await self._safe_reply(
                update.effective_chat.id,
                response.content,
                is_markdown=True,
                reply_to=update.message.message_id,
            )

            # Update last message time after successful response
            self._last_message_time = message_time

            cost = response.metadata.get("cost_usd", 0)
            if cost > 0:
                logger.debug(f"Request cost: ${cost:.4f}")

        except Exception as e:
            logger.error(f"Error handling photo: {e}", exc_info=True)
            await update.message.reply_text(
                "Sorry, I encountered an error processing your image."
            )

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

        message_time = datetime.now()
        message = Message(
            id=str(update.message.message_id),
            timestamp=message_time,
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

            # Only quote-reply if message is from earlier context (5+ min gap)
            reply_to = update.message.message_id if self._should_quote_reply(message_time) else None

            await self._safe_reply(
                update.effective_chat.id,
                response.content,
                is_markdown=True,
                reply_to=reply_to,
            )

            # Update last message time after successful response
            self._last_message_time = message_time

            cost = response.metadata.get("cost_usd", 0)
            if cost > 0.01:
                logger.info(f"Response cost: ${cost:.4f}")

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            await update.message.reply_text(f"Error: {str(e)[:200]}")
