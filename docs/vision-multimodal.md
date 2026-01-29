# Vision & Multimodal Support

Support for processing images alongside text in conversations.

## Features

- Accept images via Telegram (photos)
- Pass images to vision-capable LLMs (Claude)
- Images flow through agent delegation chains
- Base64 encoding for API compatibility

## Usage

### Telegram

Send an image to the bot with or without a caption:

```
[Send photo without caption]
→ Bot: "This image shows a sunset over mountains..."

[Send photo with caption "What's in this image?"]
→ Bot: "This image contains..."
```

### Agent Delegation

Images automatically flow through delegation chains:

```
User sends photo: "Analyze this diagram"
→ DialogAgent receives image
  → Delegates to specialized agent (if needed)
    → Specialized agent receives same image
    → Processes and returns result
  → DialogAgent composes final response
→ User gets analysis
```

## Architecture

### Message Format

Images are stored in `Message.metadata["images"]`:

```python
message = Message(
    id=str(uuid4()),
    timestamp=datetime.now(),
    role="user",
    content="What's in this image?",  # Caption or question
    content_type=ContentType.IMAGE,
    metadata={
        "images": [{
            "data": "<base64-encoded-image>",
            "media_type": "image/jpeg",
            "source": "telegram"
        }]
    }
)
```

### LLM API Format

`Message.to_llm_format()` converts to Claude's vision format:

```python
{
    "role": "user",
    "content": [
        {
            "type": "text",
            "text": "What's in this image?"
        },
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": "<base64-data>"
            }
        }
    ]
}
```

### Provider Support

| Provider | Vision Support | Notes |
|----------|---------------|-------|
| Claude | ✅ Yes | All Sonnet/Opus models |
| OpenRouter | ✅ Partial | Depends on model |
| Local | ✅ Yes | Depends on model (LLaVA, Llama 3.2 Vision, Qwen2-VL, etc.) |

## Implementation

### Telegram Interface

```python
async def _handle_photo(self, update, context):
    # Download photo from Telegram
    photo_file = await context.bot.get_file(photo.file_id)
    photo_bytes = BytesIO()
    await photo_file.download_to_memory(photo_bytes)

    # Convert to base64
    image_data = base64.b64encode(photo_bytes.read()).decode('utf-8')

    # Create message with image metadata
    message = Message(
        content=caption or "What's in this image?",
        content_type=ContentType.IMAGE,
        metadata={
            "images": [{
                "data": image_data,
                "media_type": "image/jpeg"
            }]
        }
    )

    # Process normally - vision happens automatically
    response = await self.agent.process(message)
```

### Agent Processing

No changes needed! Agents automatically handle images:

```python
# DialogAgent
async def process(self, message: Message) -> Message:
    # ... normal processing ...

    # Convert messages to LLM format (handles images automatically)
    llm_messages = [msg.to_llm_format() for msg in conversation]

    # LLM sees both text and images
    response = await self.llm.complete(llm_messages, config)
```

### Sub-Agent Delegation

Images flow through automatically via metadata:

```python
# Delegation tool passes full message
message = Message(
    content=task,
    content_type=ContentType.IMAGE,  # Preserved
    metadata={"images": [...]}  # Passed through
)

result = await specialized_agent.process(message)
```

## Image Formats Supported

- JPEG (.jpg, .jpeg)
- PNG (.png)
- GIF (.gif)
- WebP (.webp)

Max size: ~5MB (Telegram limit: 10MB compressed)

## Token Cost

Images consume additional tokens:

| Image Size | Approximate Tokens |
|------------|-------------------|
| Small (< 200KB) | ~85 tokens |
| Medium (200KB-1MB) | ~170 tokens |
| Large (1MB+) | ~255 tokens |

Example cost with Claude Sonnet:
```
Text query: 100 tokens
Image: 170 tokens
Response: 200 tokens
Total: 470 tokens @ $3/MTok = $0.00141
```

## Examples

### Simple Analysis

```
User: [Sends screenshot of code]
Bot: This code implements a binary search algorithm...
```

### With Sub-Agent

```
User: [Sends weather map] "Is it going to rain?"
→ DialogAgent: Sees image + question
  → WeatherAgent: Receives same image (if delegated)
  → Analyzes map
→ Bot: "Yes, the radar shows rain approaching from the west..."
```

### Multi-Turn

```
User: [Sends diagram]
Bot: This is a system architecture diagram...

User: "What about the database layer?"
→ Bot: "Looking at the diagram from earlier..."
  (Image still in conversation context)
```

## Local Vision Models

Many local models now support vision via Ollama, LM Studio, or vLLM:

**Recommended Models:**
- **LLaVA 1.6** (7B, 13B, 34B) - General purpose vision
- **Llama 3.2 Vision** (11B, 90B) - Meta's vision model
- **Qwen2-VL** (2B, 7B, 72B) - Strong multilingual vision
- **BakLLaVA** - Fast and efficient
- **MiniCPM-V** - Compact vision model

**Setup with Ollama:**
```bash
# Install a vision model
ollama pull llava:7b
# Or Llama 3.2 Vision
ollama pull llama3.2-vision:11b

# Configure in .env
SENTINEL_LOCAL_LLM_URL=http://localhost:11434/v1
```

**Testing Vision:**
```bash
# Test with Ollama
curl http://localhost:11434/v1/chat/completions \
  -d '{"model": "llava:7b", "messages": [...]}'
```

The local provider automatically converts image format from Claude-style to OpenAI-style, so vision "just works" if your model supports it.

## Limitations

1. **Single image per message** - Current implementation supports one image
2. **No image storage** - Images are base64 in memory only
3. **No image generation** - Input only, not output
4. **Model-dependent** - Not all local models support vision (check model docs)

## Future Enhancements

1. **Multiple images** - Support array of images per message
2. **Image persistence** - Save to memory/disk for later reference
3. **Vision-specific tools** - OCR, object detection, image classification
4. **Image generation** - DALL-E integration for creating images
5. **Smart routing** - Auto-detect if image analysis needed, use vision-capable model

## Testing

Run vision tests:

```bash
# Message format test
uv run pytest tests/integration/test_vision.py::test_vision_message_format -v

# End-to-end with Claude
uv run pytest tests/integration/test_vision.py::test_vision_with_claude -v

# Through DialogAgent
uv run pytest tests/integration/test_vision.py::test_vision_through_dialog_agent -v
```

## Troubleshooting

**"Could not process image" error**:
- Image too small (< 100 bytes) or corrupted
- Model doesn't support vision (check model capabilities)
- Unsupported format (use JPEG, PNG, WebP, GIF)

**Images not appearing in response**:
- Check model supports vision (llava, llama3.2-vision, qwen2-vl, etc.)
- Verify image in metadata: `print(message.metadata.get("images"))`
- Check logs for vision indicator: `[+X image(s)]`

**High costs with Claude**:
- Images add ~170 tokens per image
- Use local vision models (free) or OpenRouter (cheaper)
- Consider image size/quality tradeoffs

**Local model not understanding images**:
- Model may not support vision - use llava, llama3.2-vision, etc.
- Check Ollama/LM Studio logs for vision support
- Try: `ollama list` to see installed models
