"""Weather agent - provides weather information via wttr.in API."""

import json
from typing import Any, cast

import httpx

from sentinel.agents.base import LLMProvider
from sentinel.agents.tool_agent import ToolAgent
from sentinel.core.logging import get_logger
from sentinel.llm.base import LLMConfig
from sentinel.llm.router import TaskType

logger = get_logger("agents.tool_agents.weather")

EXTRACT_LOCATION_PROMPT = """Extract the location from this weather request.
Return ONLY the location name (city, region, or coordinates), nothing else.

Examples:
- "What's the weather in Tokyo?" → Tokyo
- "weather for New York City" → New York City
- "temperature in London, UK" → London, UK
- "will it rain today" → (use user's location if available, otherwise return "local")

Request: {task}
User location (if known): {user_location}

Location:"""

SUMMARIZE_WEATHER_PROMPT = """Summarize this weather data in a natural, conversational way.
Include: current conditions, temperature, and brief forecast.
Keep it concise (2-3 sentences).

Location: {location}
Current: {current}
Forecast: {forecast}

Summary:"""


class WeatherAgent(ToolAgent):
    """Agent that provides weather information using wttr.in API."""

    agent_name = "WeatherAgent"
    capability_description = "I can check current weather and forecasts for any location worldwide"

    def __init__(self, llm: LLMProvider):
        super().__init__(llm)
        self._api_base = "https://wttr.in"
        self._timeout = 10.0

    async def execute_task(self, task: str, global_context: dict[str, Any]) -> str:
        """Execute weather query.

        Args:
            task: Natural language request like "weather in Tokyo"
            global_context: May contain user_profile with default location

        Returns:
            Natural language weather summary
        """
        await self._ensure_llm_initialized()

        # Step 1: Extract location from task
        location = await self._extract_location(task, global_context)
        logger.debug(f"Extracted location: {location}")

        # Step 2: Fetch weather data
        weather_data = await self._fetch_weather(location)

        # Step 3: Summarize for user
        summary = await self._summarize_weather(location, weather_data)

        return summary

    async def _extract_location(self, task: str, global_context: dict[str, Any]) -> str:
        """Use LLM to extract location from natural language request."""
        user_location = "unknown"
        if "user_profile" in global_context:
            profile = global_context["user_profile"]
            # Could check profile.preferences.get("location") or profile.environment
            user_location = profile.environment or "unknown"

        llm_config = LLMConfig(model=None, max_tokens=50, temperature=0.1)
        messages = [
            {
                "role": "user",
                "content": EXTRACT_LOCATION_PROMPT.format(task=task, user_location=user_location),
            }
        ]

        response = await self.llm.complete(messages, llm_config, task=TaskType.TOOL_CALL)
        location = response.content.strip()

        # Handle "local" fallback
        if location.lower() == "local":
            location = user_location if user_location != "unknown" else "auto:ip"

        return location

    async def _fetch_weather(self, location: str) -> dict[str, Any]:
        """Fetch weather data from wttr.in API.

        Args:
            location: City name, region, or "auto:ip" for IP-based location

        Returns:
            Parsed JSON weather data

        Raises:
            Exception: On API failure or invalid location
        """
        # Use format=j1 for JSON, lang=en for English
        url = f"{self._api_base}/{location}"
        params = {"format": "j1", "lang": "en"}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                if "error" in data:
                    raise ValueError(f"Invalid location: {location}")

                if not isinstance(data, dict):
                    raise ValueError("Weather API returned unexpected response")
                return cast(dict[str, Any], data)

        except httpx.TimeoutException as e:
            raise TimeoutError(f"Weather API timeout for location: {location}") from e
        except httpx.HTTPError as e:
            raise Exception(f"Weather API error: {e}") from e
        except json.JSONDecodeError as e:
            raise Exception("Failed to parse weather data") from e

    async def _summarize_weather(self, location: str, data: dict[str, Any]) -> str:
        """Use LLM to create natural language summary of weather data."""
        current_condition = data.get("current_condition", [{}])[0]
        weather = data.get("weather", [{}])

        try:
            # Extract key data from wttr.in response
            current_summary = {
                "temp_c": current_condition.get("temp_C"),
                "temp_f": current_condition.get("temp_F"),
                "condition": current_condition.get("weatherDesc", [{}])[0].get("value"),
                "feels_like_c": current_condition.get("FeelsLikeC"),
                "humidity": current_condition.get("humidity"),
                "wind_kph": current_condition.get("windspeedKmph"),
            }

            # Get today and tomorrow forecast
            forecast_summary = []
            for day in weather[:2]:  # Today and tomorrow
                forecast_summary.append(
                    {
                        "date": day.get("date"),
                        "max_temp_c": day.get("maxtempC"),
                        "min_temp_c": day.get("mintempC"),
                        "condition": day.get("hourly", [{}])[4]
                        .get("weatherDesc", [{}])[0]
                        .get("value"),
                    }
                )

            # Use LLM to create friendly summary
            llm_config = LLMConfig(model=None, max_tokens=200, temperature=0.4)
            messages = [
                {
                    "role": "user",
                    "content": SUMMARIZE_WEATHER_PROMPT.format(
                        location=location,
                        current=json.dumps(current_summary, indent=2),
                        forecast=json.dumps(forecast_summary, indent=2),
                    ),
                }
            ]

            response = await self.llm.complete(messages, llm_config, task=TaskType.SUMMARIZATION)
            return response.content.strip()

        except Exception as e:
            logger.warning(f"Summarization failed, using fallback: {e}")
            # Fallback to simple summary
            temp_c = current_condition.get("temp_C", "?")
            condition = current_condition.get("weatherDesc", [{}])[0].get("value", "Unknown")
            return f"Weather in {location}: {condition}, {temp_c}°C"
