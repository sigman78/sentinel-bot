# Task Scheduling System

Persistent task scheduling and execution system for proactive agent behavior.

## Overview

Users can schedule one-time reminders and recurring tasks via natural language. Tasks execute automatically in the background and send notifications through Telegram.

**Examples:**
- "Remind me in 5 minutes to call mom"
- "/schedule daily 9am check email"
- "/schedule weekdays 6pm take a break"

## Architecture

```
User Input → Parser → TaskManager → SQLite → AwarenessAgent → Executor → Notification
```

### Components

**Task Types** (`tasks/types.py`)
- REMINDER - Simple notifications
- AGENT_TASK - Delegate to agent (future)
- API_CALL - HTTP requests (future)
- WEB_SEARCH - Search + summarize (future)

**Schedule Parser** (`tasks/parser.py`)
- Delays: "5m", "2h", "1d", "30s"
- Patterns: "daily 9am", "weekdays 6pm", "monday 10am"
- Next-run calculation with timezone awareness

**Task Manager** (`tasks/manager.py`)
- `add_reminder(delay, message)` - One-time
- `add_recurring_task(schedule, type, data)` - Recurring
- `check_and_execute_due_tasks()` - Execute due tasks
- `list_tasks()` / `cancel_task(id)` - Management

**Storage** (`memory/store.py`)
- SQLite table: `scheduled_tasks`
- Indexed on `next_run` for performance
- Persistent across restarts

**Integration**
- AwarenessAgent checks every minute for due tasks
- Telegram commands: `/remind`, `/schedule`, `/tasks`, `/cancel`
- DialogAgent handles natural language via tool calls

## Key Features

- ✅ Natural language parsing
- ✅ One-time and recurring tasks
- ✅ Automatic rescheduling after execution
- ✅ Task persistence across restarts
- ✅ Telegram integration
- ✅ Tool calling support
- ✅ Comprehensive test coverage (11 integration tests)

## Usage

**CLI / Natural Language:**
```python
"Remind me in 10 minutes to check oven"
"Set daily reminder at 9am to review calendar"
```

**Telegram Commands:**
```
/remind 5m call dentist
/schedule daily 9am morning standup
/tasks
/cancel task_123
```

**Programmatic:**
```python
from sentinel.tasks.manager import TaskManager

manager = TaskManager(memory=store, notification_callback=notify)
await manager.add_reminder("5m", "Take break")
await manager.add_recurring_task("daily 9am", "reminder", "Check email")
```

## Implementation Details

- SQLite schema includes: id, task_type, description, schedule_type, schedule_data, execution_data, enabled, created_at, last_run, next_run
- Recurring tasks advance from scheduled time (not current time) to avoid drift
- Disabled tasks after one-time execution
- Safe error handling with logging for failed executions

## Testing

Full integration test suite covers:
- End-to-end reminder flow
- Recurring task execution and rescheduling
- Multiple tasks with priority
- Persistence across restarts
- Notification failure handling
- Edge cases (weekdays, specific days, past times)

See `tests/integration/test_task_system.py` for details.
