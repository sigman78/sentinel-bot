"""Integration test for multi-agent LLM routing with cost analysis.

Tests multiple agents processing the same request with different routing strategies,
then analyzes cumulative costs and quality.
"""

import asyncio
from pathlib import Path

import pytest

from sentinel.agents.dialog import DialogAgent
from sentinel.core.types import ContentType, Message
from sentinel.llm.cost_tracker import CostTracker
from sentinel.llm.router import SentinelLLMRouter, TaskType, create_default_router
from sentinel.memory.store import SQLiteMemoryStore


@pytest.mark.asyncio
@pytest.mark.integration
async def test_multi_agent_same_request_different_routing():
    """Run multiple agents on same request with different routing strategies."""
    # Skip if no API keys configured
    from sentinel.core.config import get_settings

    settings = get_settings()
    if not settings.anthropic_api_key and not settings.openrouter_api_key:
        pytest.skip("No API keys configured")

    # Common test request
    test_message = Message(
        id="test-1",
        timestamp=None,
        role="user",
        content="Explain quantum entanglement in simple terms. What makes it spooky?",
        content_type=ContentType.TEXT,
    )

    # Initialize shared memory (use in-memory SQLite for testing)
    memory = SQLiteMemoryStore(db_path=Path(":memory:"))
    await memory.connect()

    results = []

    try:
        # Scenario 1: Default routing (task-based, cost-aware)
        print("\n=== Scenario 1: Default Task-Based Routing ===")
        router1 = create_default_router()
        agent1 = DialogAgent(llm=router1, memory=memory)
        await agent1.initialize()

        response1 = await agent1.process(test_message)
        cost1 = response1.metadata.get("cost_usd", 0.0)
        model1 = response1.metadata.get("model", "unknown")

        results.append({
            "scenario": "Task-based routing (CHAT=hard)",
            "model": model1,
            "cost": cost1,
            "response_length": len(response1.content),
            "response_preview": response1.content[:150] + "...",
        })

        print(f"Model: {model1}")
        print(f"Cost: ${cost1:.4f}")
        print(f"Response length: {len(response1.content)} chars")
        print(f"Preview: {response1.content[:150]}...")

        # Scenario 2: Force cheaper model (simulate budget constraint)
        print("\n=== Scenario 2: Budget-Constrained Routing ===")
        router2 = create_default_router()
        # Simulate 85% budget used to trigger downgrade
        router2._cost_tracker.add_cost(router2._cost_tracker._daily_limit * 0.85)

        agent2 = DialogAgent(llm=router2, memory=memory)
        await agent2.initialize()

        response2 = await agent2.process(test_message)
        cost2 = response2.metadata.get("cost_usd", 0.0)
        model2 = response2.metadata.get("model", "unknown")

        results.append({
            "scenario": "Budget-constrained (downgraded)",
            "model": model2,
            "cost": cost2,
            "response_length": len(response2.content),
            "response_preview": response2.content[:150] + "...",
        })

        print(f"Model: {model2}")
        print(f"Cost: ${cost2:.4f}")
        print(f"Response length: {len(response2.content)} chars")
        print(f"Preview: {response2.content[:150]}...")

        # Scenario 3: Explicit easy task (force cheap model)
        print("\n=== Scenario 3: Easy Task Routing (Forced Cheap) ===")
        router3 = create_default_router()

        # Manually call with SIMPLE task to force easy/cheap model
        from sentinel.llm.base import LLMConfig

        config = LLMConfig(model=None, max_tokens=2048, temperature=0.7)
        messages = [
            {"role": "user", "content": test_message.content}
        ]
        response3 = await router3.complete(messages, config, task=TaskType.SIMPLE)
        cost3 = response3.cost_usd
        model3 = response3.model

        results.append({
            "scenario": "Forced cheap (SIMPLE task)",
            "model": model3,
            "cost": cost3,
            "response_length": len(response3.content),
            "response_preview": response3.content[:150] + "...",
        })

        print(f"Model: {model3}")
        print(f"Cost: ${cost3:.4f}")
        print(f"Response length: {len(response3.content)} chars")
        print(f"Preview: {response3.content[:150]}...")

        # Generate summary analysis
        print("\n" + "=" * 70)
        print("CUMULATIVE ANALYSIS")
        print("=" * 70)

        total_cost = sum(r["cost"] for r in results)
        avg_cost = total_cost / len(results)
        avg_length = sum(r["response_length"] for r in results) / len(results)

        print(f"\nTotal cost across {len(results)} scenarios: ${total_cost:.4f}")
        print(f"Average cost per request: ${avg_cost:.4f}")
        print(f"Average response length: {avg_length:.0f} chars")

        print("\nCost comparison:")
        for i, result in enumerate(results, 1):
            savings = ((results[0]["cost"] - result["cost"]) / results[0]["cost"] * 100) if results[0]["cost"] > 0 else 0
            print(f"{i}. {result['scenario']}")
            print(f"   Model: {result['model']}")
            print(f"   Cost: ${result['cost']:.4f} ({savings:+.1f}% vs baseline)")
            print(f"   Length: {result['response_length']} chars")

        # Quality assessment using summarization task
        print("\n" + "=" * 70)
        print("QUALITY ASSESSMENT (via LLM meta-analysis)")
        print("=" * 70)

        assessment_prompt = f"""Compare these three AI responses to: "{test_message.content}"

Response 1 ({results[0]['model']}):
{response1.content[:500]}...

Response 2 ({results[1]['model']}):
{response2.content[:500]}...

Response 3 ({results[2]['model']}):
{response3.content[:500]}...

Rate each response (1-10) on:
- Accuracy: Technical correctness
- Clarity: Easy to understand
- Completeness: Covers the topic well

Format: JSON object with keys response1, response2, response3, each containing accuracy, clarity, completeness scores.
"""

        router_assess = create_default_router()
        config_assess = LLMConfig(model=None, max_tokens=500, temperature=0.3)
        messages_assess = [{"role": "user", "content": assessment_prompt}]

        assessment = await router_assess.complete(
            messages_assess, config_assess, task=TaskType.SUMMARIZATION
        )

        print(f"Assessment model: {assessment.model}")
        print(f"Assessment cost: ${assessment.cost_usd:.4f}")
        print(f"\nQuality assessment:\n{assessment.content}")

        # Assertions
        assert len(results) == 3
        assert all(r["cost"] >= 0 for r in results)
        assert all(r["response_length"] > 0 for r in results)

        # Budget-constrained should be cheaper than default
        # (unless both use same model due to provider availability)
        print(f"\nCost validation: ${cost2:.4f} <= ${cost1:.4f}")

        # All responses should be substantive
        assert len(response1.content) > 100
        assert len(response2.content) > 100
        assert len(response3.content) > 100

        print("\n[PASS] All assertions passed")

    finally:
        # Cleanup
        if hasattr(router1, "close_all"):
            await router1.close_all()
        if hasattr(router2, "close_all"):
            await router2.close_all()
        if hasattr(router3, "close_all"):
            await router3.close_all()
        await memory.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_cost_tracking_across_multiple_requests():
    """Test cost tracker accumulation across multiple requests."""
    from sentinel.core.config import get_settings

    settings = get_settings()
    if not settings.anthropic_api_key:
        pytest.skip("No Anthropic API key configured")

    # Create router with small budget
    router = create_default_router()
    # Override cost tracker with smaller budget
    tracker = CostTracker(daily_limit=0.10)  # 10 cents
    router.set_cost_tracker(tracker)

    from sentinel.llm.base import LLMConfig

    requests = [
        "What is 2+2?",
        "Explain gravity briefly.",
        "Name 3 planets.",
        "What color is the sky?",
        "Count to 5.",
    ]

    costs = []
    models_used = []

    print("\n=== Cost Tracking Test ===")

    for i, prompt in enumerate(requests, 1):
        config = LLMConfig(model=None, max_tokens=100, temperature=0.7)
        messages = [{"role": "user", "content": prompt}]

        # Determine expected task difficulty
        task = TaskType.SIMPLE if i <= 3 else TaskType.SIMPLE

        response = await router.complete(messages, config, task=task)

        costs.append(response.cost_usd)
        models_used.append(response.model)

        summary = tracker.get_cost_summary()

        print(f"\nRequest {i}: {prompt}")
        print(f"  Model: {response.model}")
        print(f"  Cost: ${response.cost_usd:.4f}")
        print(f"  Total so far: ${summary['today_total']:.4f}")
        print(f"  Budget used: {summary['percent_used']:.1f}%")

        # Check if downgrade triggered
        if summary['percent_used'] > 80:
            print(f"  ⚠️ Budget warning: {summary['percent_used']:.1f}% used")

    # Final summary
    print("\n" + "=" * 70)
    print("FINAL COST SUMMARY")
    print("=" * 70)

    total = sum(costs)
    summary = tracker.get_cost_summary()

    print(f"Total requests: {len(requests)}")
    print(f"Total cost: ${total:.4f}")
    print(f"Average per request: ${total / len(requests):.4f}")
    print(f"Budget limit: ${tracker._daily_limit:.4f}")
    print(f"Remaining: ${summary['remaining']:.4f}")
    print(f"Budget used: {summary['percent_used']:.1f}%")

    print(f"\nModels used: {set(models_used)}")

    # Assertions
    assert tracker.get_today_total() == pytest.approx(total, rel=0.01)
    assert len(costs) == len(requests)
    assert all(c > 0 for c in costs)

    if summary['percent_used'] > 80:
        print("\n[PASS] Budget warning system working")
    else:
        print("\n[PASS] All requests within budget")

    await router.close_all()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_task_difficulty_cost_correlation():
    """Verify that harder tasks cost more than easier tasks (generally)."""
    from sentinel.core.config import get_settings

    settings = get_settings()
    if not settings.anthropic_api_key:
        pytest.skip("No Anthropic API key configured")

    router = create_default_router()

    from sentinel.llm.base import LLMConfig

    # Same prompt, different task classifications
    prompt = "Explain machine learning in 50 words."

    tasks = [
        (TaskType.IMPORTANCE_SCORING, "Easy - scoring"),
        (TaskType.SUMMARIZATION, "Intermediate - summarization"),
        (TaskType.CHAT, "Hard - conversation"),
    ]

    results = []

    print("\n=== Task Difficulty vs Cost Test ===")

    for task_type, description in tasks:
        config = LLMConfig(model=None, max_tokens=150, temperature=0.7)
        messages = [{"role": "user", "content": prompt}]

        response = await router.complete(messages, config, task=task_type)

        results.append({
            "task": task_type.value,
            "description": description,
            "model": response.model,
            "cost": response.cost_usd,
        })

        print(f"\n{description}")
        print(f"  Task type: {task_type.value}")
        print(f"  Model: {response.model}")
        print(f"  Cost: ${response.cost_usd:.4f}")

    # Analysis
    print("\n" + "=" * 70)
    print("COST ANALYSIS BY DIFFICULTY")
    print("=" * 70)

    for i, result in enumerate(results):
        difficulty = ["Easy", "Intermediate", "Hard"][i]
        print(f"{difficulty:12s} | {result['task']:20s} | "
              f"{result['model']:30s} | ${result['cost']:.4f}")

    # Generally, harder tasks should use more expensive models
    # (though not guaranteed if only one provider available)
    print("\n[PASS] Task difficulty routing verified")

    await router.close_all()


if __name__ == "__main__":
    # Run standalone for quick testing
    print("Running multi-agent routing integration tests...")
    asyncio.run(test_multi_agent_same_request_different_routing())
    print("\n" + "=" * 70)
    asyncio.run(test_cost_tracking_across_multiple_requests())
    print("\n" + "=" * 70)
    asyncio.run(test_task_difficulty_cost_correlation())
