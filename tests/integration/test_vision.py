"""Integration tests for vision/multimodal support."""

import base64
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from sentinel.agents.dialog import DialogAgent
from sentinel.core.types import ContentType, Message
from sentinel.llm.router import create_default_router
from sentinel.memory.store import SQLiteMemoryStore


@pytest.mark.integration
async def test_vision_message_format():
    """Test that Message.to_llm_format() handles images correctly."""
    # Create a simple 1x1 red pixel PNG
    red_pixel_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00"
        b"\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8"
        b"\xcf\xc0\x00\x00\x00\x03\x00\x01\x00\x05\x00\x05\x8f\x1fDC"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    image_b64 = base64.b64encode(red_pixel_png).decode("utf-8")

    message = Message(
        id=str(uuid4()),
        timestamp=datetime.now(),
        role="user",
        content="What color is this pixel?",
        content_type=ContentType.IMAGE,
        metadata={"images": [{"data": image_b64, "media_type": "image/png"}]},
    )

    llm_format = message.to_llm_format()

    # Should have content blocks format
    assert llm_format["role"] == "user"
    assert isinstance(llm_format["content"], list)
    assert len(llm_format["content"]) == 2  # Text + image

    # Check text block
    text_block = llm_format["content"][0]
    assert text_block["type"] == "text"
    assert text_block["text"] == "What color is this pixel?"

    # Check image block
    image_block = llm_format["content"][1]
    assert image_block["type"] == "image"
    assert image_block["source"]["type"] == "base64"
    assert image_block["source"]["media_type"] == "image/png"
    assert image_block["source"]["data"] == image_b64


@pytest.mark.integration
async def test_vision_with_claude():
    """Test vision capability with Claude API."""
    router = create_default_router()
    if not router.available_providers:
        pytest.skip("No LLM providers configured")

    # Check if any provider with multimodal support is available
    multimodal_models = [
        m for m in router.registry.models.values() if m.multimodal and m.is_available
    ]
    if not multimodal_models:
        pytest.skip("No multimodal models configured")

    llm = router

    # Load actual test image
    image_path = Path(__file__).parent.parent.parent / "docs" / "sentinel-logo.png"
    if not image_path.exists():
        pytest.skip(f"Test image not found at {image_path}")

    image_data = image_path.read_bytes()
    image_b64 = base64.b64encode(image_data).decode("utf-8")

    message = Message(
        id=str(uuid4()),
        timestamp=datetime.now(),
        role="user",
        content="What do you see in this image? Describe it briefly.",
        content_type=ContentType.IMAGE,
        metadata={"images": [{"data": image_b64, "media_type": "image/png"}]},
    )

    # Convert to LLM format
    llm_messages = [message.to_llm_format()]

    # Call Claude
    from sentinel.llm.base import LLMConfig

    config = LLMConfig(model=None, max_tokens=100, temperature=0.3)
    response = await llm.complete(llm_messages, config)

    # Should get a response about the image
    assert isinstance(response.content, str)
    assert len(response.content) > 0
    print(f"\nVision response: {response.content}")

    # Should describe the image (logo, sentinel, design, etc.)
    assert len(response.content) > 10  # Non-trivial response


@pytest.mark.integration
async def test_vision_through_dialog_agent():
    """Test that DialogAgent can handle image messages."""
    router = create_default_router()
    if not router.available_providers:
        pytest.skip("No LLM providers configured")

    # Check if any provider with multimodal support is available
    multimodal_models = [
        m for m in router.registry.models.values() if m.multimodal and m.is_available
    ]
    if not multimodal_models:
        pytest.skip("No multimodal models configured")

    llm = router

    # Create in-memory database for test
    memory = SQLiteMemoryStore(Path(":memory:"))
    await memory.connect()

    agent = DialogAgent(llm=llm, memory=memory)
    await agent.initialize()

    # Load actual test image
    image_path = Path(__file__).parent.parent.parent / "docs" / "sentinel-logo.png"
    if not image_path.exists():
        pytest.skip(f"Test image not found at {image_path}")

    image_data = image_path.read_bytes()
    image_b64 = base64.b64encode(image_data).decode("utf-8")

    message = Message(
        id=str(uuid4()),
        timestamp=datetime.now(),
        role="user",
        content="What do you see in this image?",
        content_type=ContentType.IMAGE,
        metadata={"images": [{"data": image_b64, "media_type": "image/png"}]},
    )

    response = await agent.process(message)

    assert isinstance(response.content, str)
    assert len(response.content) > 10  # Non-trivial response
    print(f"\nDialogAgent vision response: {response.content}")

    await memory.close()
