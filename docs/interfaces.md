# Interfaces

## Overview

Interfaces are adapters between human communication channels and the Orchestrator.

```
Human ←→ Interface Adapter ←→ Orchestrator ←→ Agents
```

All interfaces implement common protocol:
```python
class Interface(Protocol):
    async def receive(self) -> InboundMessage: ...
    async def send(self, msg: OutboundMessage) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
```

## Telegram Bot (Primary)

### Setup
- Bot created via @BotFather
- Webhook or long-polling mode
- Single-user mode (owner only) for v1

### Message Types

| Telegram | Internal | Notes |
|----------|----------|-------|
| Text | `TextMessage` | Standard input |
| Voice | `VoiceMessage` | Transcribe via Whisper/API |
| Photo | `ImageMessage` | Vision-capable LLM |
| Document | `FileMessage` | Parse if supported |
| Sticker/Reaction | `ReactionMessage` | Sentiment signal |

### Features
- Markdown formatting in responses
- Inline keyboards for choices
- Message threading (reply chains)
- Typing indicator during processing

### Implementation
```python
# src/sentinel/interfaces/telegram.py
class TelegramInterface:
    def __init__(self, token: str, owner_id: int):
        self.bot = Bot(token)
        self.owner_id = owner_id  # Only respond to owner

    async def receive(self) -> InboundMessage:
        update = await self.bot.get_updates()
        return self._convert(update)

    async def send(self, msg: OutboundMessage) -> None:
        await self.bot.send_message(
            chat_id=self.owner_id,
            text=msg.content,
            parse_mode="Markdown"
        )
```

## CLI (Development)

Simple stdin/stdout interface for testing.

```python
class CLIInterface:
    async def receive(self) -> InboundMessage:
        line = await asyncio.get_event_loop().run_in_executor(
            None, input, "> "
        )
        return TextMessage(content=line)

    async def send(self, msg: OutboundMessage) -> None:
        print(f"[Sentinel]: {msg.content}")
```

## Future Interfaces

| Interface | Priority | Notes |
|-----------|----------|-------|
| Voice (real-time) | Medium | WebRTC or phone integration |
| Web UI | Low | Dashboard, memory browser |
| API | Low | Programmatic access |
| Email | Low | Async long-form communication |

## Message Protocol

### Inbound
```python
@dataclass
class InboundMessage:
    id: str
    timestamp: datetime
    source: InterfaceType
    content: str | bytes
    content_type: ContentType  # text, voice, image, file
    metadata: dict  # Interface-specific data
```

### Outbound
```python
@dataclass
class OutboundMessage:
    content: str
    format: OutputFormat  # plain, markdown, html
    attachments: list[Attachment]
    reply_to: str | None  # Message ID to reply to
    actions: list[Action]  # Buttons, choices
```

## Multi-Interface Coordination

- User identified by global ID, mapped from interface-specific IDs
- Conversation continuity across interfaces
- Interface preference stored in user profile
- Notifications routed to preferred interface
