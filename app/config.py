"""Central configuration for Outdoor Nudge.

Every value is overridable with an environment variable (see .env.example);
the defaults below preserve the original behaviour so nothing changes unless
the user explicitly opts in.
"""
import os

# --- Ollama ---------------------------------------------------------------
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("NUDGE_MODEL", "llama3.2:3b")

# --- Weather / location ---------------------------------------------------
OPEN_METEO_URL = os.environ.get(
    "OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast"
)
DEFAULT_LAT = float(os.environ.get("NUDGE_LAT", "44.4268"))
DEFAULT_LON = float(os.environ.get("NUDGE_LON", "26.1025"))
WEATHER_TIMEOUT = float(os.environ.get("NUDGE_WEATHER_TIMEOUT", "12"))

# --- Paths (resolved relative to the repo root) ---------------------------
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_FILE = os.environ.get("NUDGE_INDEX_FILE") or os.path.join(_ROOT, "static", "index.html")
HISTORY_FILE = os.environ.get("NUDGE_HISTORY_FILE") or os.path.join(_ROOT, "data", "history.json")
