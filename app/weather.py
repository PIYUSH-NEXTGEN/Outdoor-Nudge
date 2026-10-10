"""Weather fetching (Open-Meteo) and day-part helpers."""
import requests

from .config import OPEN_METEO_URL, WEATHER_TIMEOUT

def wmo_to_text(code: int) -> str:
    mapping = {
        0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
        45: "fog", 48: "depositing rime fog",
        51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
        56: "light freezing drizzle", 57: "dense freezing drizzle",
        61: "slight rain", 63: "moderate rain", 65: "heavy rain",
        66: "light freezing rain", 67: "heavy freezing rain",
        71: "slight snow", 73: "moderate snow", 75: "heavy snow", 77: "snow grains",
        80: "slight rain showers", 81: "moderate rain showers", 82: "violent rain showers",
        85: "slight snow showers", 86: "heavy snow showers",
        95: "thunderstorm", 96: "thunderstorm with slight hail", 99: "thunderstorm with heavy hail",
    }
    return mapping.get(code, f"unknown code {code}")


def part_of_day(hour: int) -> str:
    if 5 <= hour < 11:
        return "morning"
    if 11 <= hour < 14:
        return "midday"
    if 14 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 22:
        return "evening"
    return "night"


def fetch_weather(lat: float, lon: float) -> dict:
    params = {
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,precipitation,wind_speed_10m,weather_code,is_day",
        "timezone": "auto",
    }
    try:
        r = requests.get(OPEN_METEO_URL, params=params, timeout=WEATHER_TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        raise RuntimeError(f"Open-Meteo request failed: {e}")
    try:
        cur = data["current"]
        code = int(cur["weather_code"])
        return {
            "lat": lat, "lon": lon,
            "temperature_c": cur.get("temperature_2m"),
            "precipitation_mm": cur.get("precipitation"),
            "wind_kph": cur.get("wind_speed_10m"),
            "weather_code": code,
            "description": wmo_to_text(code),
            "is_day": bool(cur.get("is_day")),
            "time": cur.get("time"),
        }
    except Exception as e:
        raise RuntimeError(f"Unexpected Open-Meteo response: {e} | raw={str(data)[:400]}")
