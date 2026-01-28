# Task Management System Implementation (Part A)

## Overview

Implemented a persistent task scheduling and execution system that enables proactive agent behavior. Users can schedule one-time reminders and recurring tasks that execute automatically in the background.

## Components Implemented

### 1. Task Types (`src/sentinel/tasks/types.py`)
- `TaskType` enum: REMINDER, AGENT_TASK, API_CALL, WEB_SEARCH
- `ScheduledTask` dataclass with serialization methods
- Currently only REMINDER is fully implemented

### 2. Schedule Parser (`src/sentinel/tasks/parser.py`)
- Parse time delays: "5m", "2h", "1d", "30s"
- Parse recurring patterns:
  - "daily 9am" - Every day at 9am
  - "weekdays 6pm" - Monday-Friday at 6pm
  - "monday 10am" - Every Monday at 10am
- Calculate next run times for recurring tasks
- Handles edge cases: past times, weekends, specific days

### 3. Database Schema (`src/sentinel/memory/store.py`)
Added `scheduled_tasks` table:
- Persistent storage across restarts
- Index on `next_run` for efficient queries
- CRUD operations: create, get, list, update, delete
- Query for due tasks

### 4. Task Executor (`src/sentinel/tasks/executor.py`)
- Execute different task types
- REMINDER: Send notification via callback
- AGENT_TASK, API_CALL, WEB_SEARCH: Stubs for future implementation
- Error handling and logging

### 5. Task Manager (`src/sentinel/tasks/manager.py`)
High-level orchestration:
- `add_reminder(delay, message)` - One-time reminder
- `add_recurring_task(schedule, type, description)` - Recurring task
- `list_tasks()` - List active tasks
- `cancel_task(task_id)` - Cancel task
- `check_and_execute_due_tasks()` - Check and execute due tasks
- Reschedule recurring tasks after execution

### 6. Telegram Integration (`src/sentinel/interfaces/telegram.py`)
New commands:
- `/remind <time> <message>` - Set one-time reminder
- `/schedule <pattern> <task>` - Schedule recurring task
- `/tasks` - List active tasks
- `/cancel <task_id>` - Cancel task

Updated:
- Added TaskManager initialization
- Awareness check now includes task execution
- Help text updated with new commands

## Usage Examples

### One-time Reminders
```
/remind 5m call mom
/remind 2h check oven
/remind 1d submit report
```

### Recurring Tasks
```
/schedule daily 9am check news
/schedule weekdays 6pm workout reminder
/schedule monday 10am weekly review
```

### Task Management
```
/tasks - List all active tasks
/cancel abc123 - Cancel task by ID
```

## Testing

Created comprehensive test suites:

**test_tasks_parser.py** (13 tests)
- Delay parsing (minutes, hours, days, seconds)
- Recurring pattern parsing (daily, weekdays, specific days)
- Next run calculation with various edge cases

**test_tasks_manager.py** (7 tests)
- Adding reminders and recurring tasks
- Executing due tasks
- Rescheduling recurring tasks
- Canceling tasks
- Error handling for invalid formats

All 93 tests pass (including existing tests).

## Architecture Decisions

### Simplifications Made
1. **REMINDER only** - Other task types (AGENT_TASK, API_CALL, WEB_SEARCH) deferred to Part B
2. **Simple patterns** - No full cron support yet, just common patterns
3. **No approval workflow** - Tasks execute automatically (Phase 7 will add safety)
4. **Time parsing only** - No natural language parsing ("in 5 minutes", "tomorrow at 9am")

### Key Design Choices
1. **Persistent storage** - Tasks survive restarts via SQLite
2. **Separation of concerns**:
   - Parser: Time parsing logic
   - Executor: Task execution logic
   - Manager: High-level orchestration
   - Store: Database operations
3. **Async callback** - Notifications sent via callback for flexibility
4. **Recurring task rescheduling** - Automatic recalculation of next_run
5. **One-time task cleanup** - Disabled after execution

## Future Enhancements (Part B)

1. **Tool Calling Framework**
   - LLM-driven tool selection
   - Natural language → structured tool calls
   - Tool registry and execution

2. **Additional Task Types**
   - AGENT_TASK: Delegate to DialogAgent/CodeAgent
   - API_CALL: HTTP requests to external services
   - WEB_SEARCH: Search and summarize results

3. **Advanced Scheduling**
   - Full cron support via croniter library
   - Natural language parsing ("in 5 minutes", "tomorrow")
   - Timezone handling
   - DST awareness

4. **Safety Features**
   - Approval workflow for dangerous tasks
   - Task execution history
   - Rate limiting
   - Allowlist/blocklist for API calls

## Integration Points

1. **AwarenessAgent** - Keeps existing reminder/monitor system
2. **Orchestrator** - Task checking runs every minute via background task
3. **Memory Store** - Extended with task persistence
4. **Telegram Interface** - New commands wired in

## Files Modified

- `src/sentinel/memory/store.py` - Added task table and CRUD
- `src/sentinel/interfaces/telegram.py` - Added TaskManager and commands

## Files Created

- `src/sentinel/tasks/__init__.py`
- `src/sentinel/tasks/types.py`
- `src/sentinel/tasks/parser.py`
- `src/sentinel/tasks/executor.py`
- `src/sentinel/tasks/manager.py`
- `tests/test_tasks_parser.py`
- `tests/test_tasks_manager.py`
- `docs/tool_calling_design.md`
- `docs/task_system_implementation.md`

## Performance Considerations

- Task checking runs every minute (configurable)
- Index on `next_run` for efficient queries
- Only enabled tasks are queried
- Tasks executed sequentially (can be parallelized if needed)

## Backwards Compatibility

No breaking changes. Existing AwarenessAgent reminder/monitor system remains functional alongside the new task system.
