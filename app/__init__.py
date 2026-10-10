"""Outdoor Nudge backend package (FastAPI + local Ollama + Open-Meteo, no paid APIs).

Run the server:
    uvicorn app.main:app --host 127.0.0.1 --port 8000

The package is split into focused modules (config, prompts, validation, weather,
llm, history, main). This __init__ re-exports the public API as a convenience
facade so callers -- and the test-suite -- can simply ``import app`` and use
``app.safety_violations`` etc. without reaching into submodules.
"""
from .config import (DEFAULT_LAT, DEFAULT_LON, DEFAULT_MODEL, OLLAMA_HOST,
                     OPEN_METEO_URL, WEATHER_TIMEOUT, HISTORY_FILE, INDEX_FILE)
from .prompts import (TASK_CATEGORIES, LOW_ENERGY_CATS, HIGH_ENERGY_CATS,
                      MEDIUM_ENERGY_CATS, SYSTEM_PROMPT)
from .weather import fetch_weather, part_of_day, wmo_to_text
from .history import load_history, write_history, save_history_entry, recent_titles
from .llm import call_ollama_json
from .validation import (safety_violations, validate_nudge, is_night_request,
                         energy_pool, cap_categories, pick_category, first_verb,
                         banned_verbs, CATEGORY_CAP, VENUE_BAN, LONELY_MOOD_RE,
                         CONTACT_RE)

__all__ = [
    # config
    "DEFAULT_LAT", "DEFAULT_LON", "DEFAULT_MODEL", "OLLAMA_HOST", "OPEN_METEO_URL",
    "WEATHER_TIMEOUT", "HISTORY_FILE", "INDEX_FILE",
    # prompts
    "TASK_CATEGORIES", "LOW_ENERGY_CATS", "HIGH_ENERGY_CATS", "MEDIUM_ENERGY_CATS",
    "SYSTEM_PROMPT",
    # weather
    "fetch_weather", "part_of_day", "wmo_to_text",
    # history
    "load_history", "write_history", "save_history_entry", "recent_titles",
    # llm
    "call_ollama_json",
    # validation
    "safety_violations", "validate_nudge", "is_night_request", "energy_pool",
    "cap_categories", "pick_category", "first_verb", "banned_verbs", "CATEGORY_CAP",
    "VENUE_BAN", "LONELY_MOOD_RE", "CONTACT_RE",
]
