"""HTTP agent using curl - demonstrates API testing capabilities."""

from sentinel.agents.agentic_cli import AgenticCliConfig, CliTool, SafetyLimits

config = AgenticCliConfig(
    name="HttpAgent",
    description="I can make HTTP requests, test APIs, and fetch web content using curl",
    tools=[
        CliTool.from_command(
            name="curl",
            command="curl",
            auto_help=True,
            examples=[
                "curl https://api.github.com",
                "curl -I https://example.com",
                "curl -X POST -H 'Content-Type: application/json' -d '{\"key\":\"value\"}' https://api.example.com",
                "curl -s https://httpbin.org/json",
            ],
        ),
    ],
    limits=SafetyLimits(
        timeout_seconds=60,
        max_iterations=10,
        max_consecutive_errors=2,
        max_total_errors=4,
    ),
)
