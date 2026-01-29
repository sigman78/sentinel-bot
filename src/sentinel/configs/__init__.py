"""Agent configurations.

To add a new CLI agent:
1. Create a new .py file in this directory with AgenticCliConfig
2. Import it here
3. Add to CLI_AGENT_CONFIGS list
"""

from sentinel.configs.curl_agent import config as http_agent_config
from sentinel.configs.file_agent import config as file_agent_config

# List of all CLI agent configs - add new agents here
CLI_AGENT_CONFIGS = [
    http_agent_config,
    file_agent_config,
]

__all__ = ["CLI_AGENT_CONFIGS"]
