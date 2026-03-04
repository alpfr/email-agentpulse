"""
Example tools: mock weather lookup.

Demonstrates:
  • Simulated network latency (asyncio.sleep)
  • Retries with backoff (max_retries=2)
  • Handling unknown inputs gracefully
"""

from __future__ import annotations

import asyncio
import random

from ..tools import ToolRegistry, agent_tool

# Dedicated registry for weather tools
weather_registry = ToolRegistry()

# ── Mock weather data ──
_WEATHER_DATA: dict[str, dict] = {
    "new york": {
        "city": "New York",
        "temp_f": 72,
        "temp_c": 22,
        "condition": "Partly Cloudy",
        "humidity": 65,
        "wind_mph": 12,
    },
    "london": {
        "city": "London",
        "temp_f": 59,
        "temp_c": 15,
        "condition": "Overcast",
        "humidity": 80,
        "wind_mph": 8,
    },
    "tokyo": {
        "city": "Tokyo",
        "temp_f": 77,
        "temp_c": 25,
        "condition": "Sunny",
        "humidity": 55,
        "wind_mph": 5,
    },
    "sydney": {
        "city": "Sydney",
        "temp_f": 68,
        "temp_c": 20,
        "condition": "Clear",
        "humidity": 50,
        "wind_mph": 15,
    },
    "paris": {
        "city": "Paris",
        "temp_f": 64,
        "temp_c": 18,
        "condition": "Light Rain",
        "humidity": 75,
        "wind_mph": 10,
    },
    "san francisco": {
        "city": "San Francisco",
        "temp_f": 62,
        "temp_c": 17,
        "condition": "Foggy",
        "humidity": 85,
        "wind_mph": 18,
    },
}


@agent_tool(
    name="get_weather",
    description=(
        "Get the current weather for a city. "
        "Returns temperature (F/C), condition, humidity, and wind speed. "
        "Supported cities: New York, London, Tokyo, Sydney, Paris, San Francisco."
    ),
    timeout_seconds=10,
    max_retries=2,
    idempotent=True,
    registry=weather_registry,
)
async def get_weather(city: str) -> dict:
    """Look up current weather for a city (mock data)."""
    # Simulate network latency (200–800ms)
    await asyncio.sleep(random.uniform(0.2, 0.8))

    lookup = city.strip().lower()
    data = _WEATHER_DATA.get(lookup)

    if data is None:
        return {
            "city": city,
            "error": f"Weather data not available for '{city}'.",
            "available_cities": [d["city"] for d in _WEATHER_DATA.values()],
        }

    return data


@agent_tool(
    name="compare_weather",
    description=(
        "Compare weather between two cities. "
        "Returns both cities' weather side by side with temperature difference."
    ),
    timeout_seconds=15,
    max_retries=1,
    idempotent=True,
    registry=weather_registry,
)
async def compare_weather(city_a: str, city_b: str) -> dict:
    """Compare weather between two cities."""
    # Simulate network latency
    await asyncio.sleep(random.uniform(0.3, 0.6))

    lookup_a = city_a.strip().lower()
    lookup_b = city_b.strip().lower()

    data_a = _WEATHER_DATA.get(lookup_a, {"city": city_a, "temp_f": None, "condition": "Unknown"})
    data_b = _WEATHER_DATA.get(lookup_b, {"city": city_b, "temp_f": None, "condition": "Unknown"})

    result = {
        "city_a": data_a,
        "city_b": data_b,
    }

    if data_a.get("temp_f") is not None and data_b.get("temp_f") is not None:
        result["temp_difference_f"] = abs(data_a["temp_f"] - data_b["temp_f"])
        result["warmer_city"] = data_a["city"] if data_a["temp_f"] > data_b["temp_f"] else data_b["city"]

    return result
