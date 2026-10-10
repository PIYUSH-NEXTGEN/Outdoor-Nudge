"""History persistence (history.json) with atomic writes."""
import json
import os
import uuid

from .config import HISTORY_FILE

def load_history() -> list:
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def write_history(hist: list):
    """Atomically persist the whole history list."""
    try:
        tmp = HISTORY_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False, indent=2)
        os.replace(tmp, HISTORY_FILE)
    except Exception:
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(hist, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


def save_history_entry(entry: dict):
    hist = load_history()
    # avoid exact-duplicate saves from parallel retries
    if hist and hist[-1].get("title") == entry.get("title") and hist[-1].get("mood") == entry.get("mood"):
        return
    entry.setdefault("id", uuid.uuid4().hex[:12])
    entry.setdefault("done", False)
    hist.append(entry)
    write_history(hist)


def recent_titles(n: int = 10) -> list:
    return [h.get("title", "") for h in load_history()[-n:] if h.get("title")]
