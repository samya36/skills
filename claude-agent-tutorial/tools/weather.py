"""Weather MCP tools powered by the Open-Meteo API."""

from __future__ import annotations

import json
import os
import ssl
from typing import Any

import httpx
from claude_agent_sdk import tool

API_BASE = "https://api.open-meteo.com/v1"
USER_AGENT = "cc-agent-weather/1.0"
TIMEOUT = httpx.Timeout(30.0)


def _build_ssl_context() -> ssl.SSLContext:
    """Create SSL context that optionally trusts a custom CA bundle."""
    context = ssl.create_default_context()
    custom_ca = os.environ.get("WEATHER_CA_BUNDLE") or os.environ.get("REQUESTS_CA_BUNDLE")
    if custom_ca:
        try:
            context.load_verify_locations(cafile=custom_ca)
        except Exception as error:
            print(f"Failed to load custom CA bundle: {error}")
    return context


SSL_CONFIG = _build_ssl_context()


async def _make_openmeteo_request(url: str) -> dict[str, Any] | None:
    """Make request with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(verify=SSL_CONFIG, timeout=TIMEOUT) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
    except ssl.SSLError as error:
        print(f"SSL error: {error}")
        return None
    except httpx.HTTPStatusError as error:
        print(f"HTTP error {error.response.status_code}: {error}")
        return None
    except Exception as error:
        print(f"Request failed: {error}")
        return None


def _format_tool_message(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}]}


def _parse_coordinates(args: dict[str, Any]) -> tuple[float | None, float | None, str | None]:
    """Extract and validate latitude/longitude arguments."""
    try:
        latitude = float(args["latitude"])
        longitude = float(args["longitude"])
    except KeyError as missing_key:
        return None, None, f"Missing required argument: {missing_key.args[0]}"
    except (TypeError, ValueError):
        return None, None, "Latitude and longitude must be numeric."

    if not -90 <= latitude <= 90:
        return None, None, "Latitude must be between -90 and 90 degrees."
    if not -180 <= longitude <= 180:
        return None, None, "Longitude must be between -180 and 180 degrees."

    return latitude, longitude, None


def _format_current_weather(data: dict[str, Any]) -> str:
    current = data.get("current", {})
    current_units = data.get("current_units", {})
    location = f"{data.get('latitude', '?')}, {data.get('longitude', '?')}"

    rows = [f"Current weather for {location}:"]
    metrics = {
        "temperature_2m": "Temperature",
        "apparent_temperature": "Feels like",
        "relative_humidity_2m": "Humidity",
        "precipitation": "Precipitation",
        "weather_code": "Weather code",
    }

    for key, label in metrics.items():
        value = current.get(key)
        if value is None:
            continue
        unit = current_units.get(key, "")
        rows.append(f"- {label}: {value} {unit}".rstrip())

    if len(rows) == 1:
        # No metrics found—fallback to raw JSON.
        rows.append(json.dumps(current, indent=2))

    return "\n".join(rows)


def _format_forecast(data: dict[str, Any]) -> str:
    daily = data.get("daily", {})
    daily_units = data.get("daily_units", {})
    times = daily.get("time", [])

    if not times:
        return "Forecast data not available."

    location = f"{data.get('latitude', '?')}, {data.get('longitude', '?')}"
    results = [f"Daily forecast for {location}:"]

    for index, date in enumerate(times):
        lines = [f"Date: {date}"]
        for key, label in {
            "temperature_2m_max": "Max Temp",
            "temperature_2m_min": "Min Temp",
            "precipitation_sum": "Precipitation",
            "weather_code": "Weather code",
        }.items():
            values = daily.get(key, [])
            if index >= len(values):
                continue
            unit = daily_units.get(key, "")
            lines.append(f"{label}: {values[index]} {unit}".rstrip())
        results.append("\n".join(lines))

    return "\n\n".join(results)


@tool(
    "get_current_weather",
    "Get current weather for a latitude/longitude using Open-Meteo.",
    {"latitude": float, "longitude": float},
)
async def get_current_weather(args: dict[str, Any]) -> dict[str, Any]:
    """Get current weather for a location."""
    latitude, longitude, error = _parse_coordinates(args)
    if error:
        return _format_tool_message(f"Error: {error}")

    url = (
        f"{API_BASE}/forecast?latitude={latitude}&longitude={longitude}"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
        "precipitation,weather_code"
    )
    data = await _make_openmeteo_request(url)
    if not data:
        return _format_tool_message("Unable to fetch weather data right now.")

    return _format_tool_message(_format_current_weather(data))


@tool(
    "get_forecast",
    "Get multi-day forecast for a latitude/longitude using Open-Meteo.",
    {"latitude": float, "longitude": float},
)
async def get_forecast(args: dict[str, Any]) -> dict[str, Any]:
    """Get weather forecast for a location."""
    latitude, longitude, error = _parse_coordinates(args)
    if error:
        return _format_tool_message(f"Error: {error}")

    url = (
        f"{API_BASE}/forecast?latitude={latitude}&longitude={longitude}"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code"
        "&timezone=auto"
    )
    data = await _make_openmeteo_request(url)
    if not data:
        return _format_tool_message("Unable to fetch forecast data right now.")

    return _format_tool_message(_format_forecast(data))
