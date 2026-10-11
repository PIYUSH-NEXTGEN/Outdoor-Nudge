"""FastAPI routes for Outdoor Nudge. Thin layer over app.config/prompts/validation/
weather/llm/history. Run: uvicorn app.main:app --host 127.0.0.1 --port 8000
"""
import json
import os
import random
import uuid
from datetime import datetime

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .config import DEFAULT_LAT, DEFAULT_LON, DEFAULT_MODEL, INDEX_FILE, OLLAMA_HOST
from .history import load_history, save_history_entry, recent_titles, write_history
from .llm import call_ollama_json
from .prompts import SYSTEM_PROMPT, TASK_CATEGORIES
from .validation import (banned_verbs, cap_categories, energy_pool, is_night_request,
                         pick_category, validate_nudge)
from .weather import fetch_weather, part_of_day

app = FastAPI(title="Outdoor Nudge")


class NudgeRequest(BaseModel):
    mood: str = Field(..., min_length=1)
    lat: float | None = None
    lon: float | None = None
    model: str | None = None
    weather_override: str | None = None
    exclude: list[str] | None = None
    easier: bool = False
    # Test-only: ISO time (e.g. "2026-01-01T23:30") to force day/evening/night without
    # touching the server clock. Ignored (falls back to real now) when absent/invalid.
    now_override: str | None = None


@app.get("/")
def root():
    if os.path.exists(INDEX_FILE):
        return FileResponse(INDEX_FILE, media_type="text/html")
    return JSONResponse({"message": "Outdoor Nudge API. Placeholder index missing."})


@app.get("/api/weather")
def api_weather(lat: float = Query(default=DEFAULT_LAT), lon: float = Query(default=DEFAULT_LON)):
    try:
        return fetch_weather(lat, lon)
    except RuntimeError as e:
        return JSONResponse({"error": str(e)}, status_code=502)


@app.get("/api/models")
def api_models():
    import re
    try:
        import ollama
        client = ollama.Client(host=OLLAMA_HOST)
        data = client.list()
        raw = []
        items = data.models if hasattr(data, "models") else data.get("models", [])
        for m in items:
            if isinstance(m, dict):
                raw.append(m.get("name") or m.get("model") or str(m))
            else:
                raw.append(getattr(m, "model", None) or str(m))
        raw = [m for m in raw if m and m != "None"]
        # chat-capable models only: drop embedding / blob / llamacpp / rerank entries, dedupe
        NON_CHAT_RE = re.compile(r"embed|blob|llamacpp|rerank|moderation", re.IGNORECASE)
        models = list(dict.fromkeys(m for m in raw if not NON_CHAT_RE.search(m)))
        if not models:  # everything filtered out: fall back to deduped raw list
            models = list(dict.fromkeys(raw))
        return {"models": models, "host": OLLAMA_HOST}
    except Exception as e:
        msg = str(e)
        if "refused" in msg.lower() or "connect" in msg.lower():
            return JSONResponse({"error": f"Cannot reach Ollama at {OLLAMA_HOST}. Start it with 'ollama serve'."}, status_code=502)
        return JSONResponse({"error": f"Ollama list failed: {msg[:400]}"}, status_code=502)


@app.get("/api/history")
def api_history():
    return {"history": load_history()}


class DoneRequest(BaseModel):
    id: str = Field(..., min_length=1)


@app.post("/api/done")
def api_done(req: DoneRequest):
    """Mark a history entry as done (persisted in history.json)."""
    hist = load_history()
    for h in hist:
        if h.get("id") == req.id:
            if not h.get("done"):
                h["done"] = True
                h["done_at"] = datetime.now().isoformat(timespec="seconds")
                write_history(hist)
            return {"ok": True, "entry": h}
    return JSONResponse({"error": f"No history entry with id '{req.id}'."}, status_code=404)


@app.post("/api/nudge")
def api_nudge(req: NudgeRequest):
    mood = (req.mood or "").strip()
    if not mood:
        return JSONResponse({"error": "Field 'mood' must be a non-empty string."}, status_code=400)
    lat = req.lat if req.lat is not None else DEFAULT_LAT
    lon = req.lon if req.lon is not None else DEFAULT_LON
    model = (req.model or DEFAULT_MODEL).strip() or DEFAULT_MODEL

    if req.weather_override and req.weather_override.strip():
        weather = {"description": req.weather_override.strip(), "override": True, "lat": lat, "lon": lon}
        weather_text = f"{weather['description']} (manual override)"
    else:
        try:
            weather = fetch_weather(lat, lon)
            weather_text = (
                f"{weather['description']}, {weather['temperature_c']}C, "
                f"precip {weather['precipitation_mm']}mm, wind {weather['wind_kph']} kph, "
                f"{'daytime' if weather['is_day'] else 'nighttime'}"
            )
        except RuntimeError as e:
            return JSONResponse({"error": str(e)}, status_code=502)

    # Test-only clock override: lets tests force day / evening / night deterministically.
    now = datetime.now()
    if req.now_override and str(req.now_override).strip():
        try:
            now = datetime.fromisoformat(str(req.now_override).strip())
        except ValueError:
            pass  # invalid override -> fall back to real time (no behavior change)
    pod = part_of_day(now.hour)
    time_str = now.strftime("%Y-%m-%d %H:%M local")
    night = is_night_request(pod, now.hour, mood)

    auto_exclude = recent_titles(10)
    exclude = list(dict.fromkeys([*auto_exclude, *(req.exclude or [])]))
    category, forced_energy = pick_category(mood, bool(req.easier), exclude)
    cat_desc = TASK_CATEGORIES.get(category, "")

    def build_prompt(cat: str) -> str:
        desc = TASK_CATEGORIES.get(cat, "")
        night_line = (
            "NIGHT_RULE: ACTIVE - keep the task within sight of their own door, doorstep, "
            "balcony or window; no walking away from home; no interacting with strangers; "
            "a doorstep/balcony/window task IS allowed.\n"
        ) if night else "NIGHT_RULE: inactive (normal daytime rules apply)\n"
        return (
            f"MOOD: {mood}\nWEATHER: {weather_text}\nLOCAL TIME: {time_str} ({pod})\n"
            f"{night_line}"
            f"LOW_ENERGY: {str(bool(req.easier)).lower()}\n"
            f"FORCED_ENERGY: {forced_energy}\n"
            f"CATEGORY: {cat}\nCATEGORY MEANS: {desc}\n"
            f"EXCLUDE (do not repeat or paraphrase these past titles): {json.dumps(exclude)}\n"
            f"BANNED VERBS (do not use in title or task): {json.dumps(sorted(banned_verbs(exclude)))}\n"
            "Suggest the one outdoor task now, JSON only."
        )

    user_prompt = build_prompt(category)
    nudge = None
    first_err = ""
    last_reason = ""
    # up to 4 attempts; attempts 2+ use a FRESH random category from the same pool
    _, pool = energy_pool(mood, bool(req.easier))
    tried = {category}
    for attempt in range(4):
        try:
            parsed = call_ollama_json(model, SYSTEM_PROMPT, user_prompt)
            nudge, reason = validate_nudge(parsed, category, exclude, forced_energy, mood, night)
            last_reason = reason
            if nudge is None and not first_err:
                first_err = f"validation:{reason}"
        except ValueError as e:
            nudge = None
            if not first_err:
                first_err = str(e)
            last_reason = str(e)
        except RuntimeError as e:
            return JSONResponse({"error": str(e)}, status_code=502)
        if nudge is not None:
            break
        # pick a fresh category for the next attempt
        eligible = cap_categories(pool)
        fresh = [c for c in eligible if c not in tried]
        if not fresh:
            # all eligible categories already tried: reuse one (bounded by the attempt loop)
            fresh = [c for c in eligible if c != category] or eligible
        if not fresh:
            break
        category = random.choice(fresh)
        tried.add(category)
        user_prompt = (build_prompt(category)
                       + f"\nYour previous reply was invalid: {last_reason}. Fix that specific problem "
                       + "(never instruct eating/tasting or bare-hand contact with plants or litter; "
                       + "no climbing, furniture, roads or water; no assumed objects like bench/bin/"
                       + "bag/paper/notebook/balcony unless the mood names them; no bare walks or "
                       + "ordinary chores; night = own doorstep/a window/balcony-if-you-have-one only, "
                       + "no walking away, no strangers, and QUIET movement only (stretching, slow "
                       + "breathing, standing balance - no jumping jacks/marching); if lonely at night, "
                       + "only send a short message/voice note, call a friend, or wave at a lit window "
                       + "or a neighbour at their door; if lonely by day, the contact must be a REAL "
                       + "person (neighbour/passerby/friend/family), never an object like shadows or "
                       + "streetlights; scavenger items must be UNIVERSAL (something round, something "
                       + "older than you, three different greens) - never a red door/crooked sign/"
                       + "feather/unevenness; sketch/write in your phone's notes app, never only 'in "
                       + "your head'; venue words only if the mood names them; match the category/"
                       + "energy rules) "
                       + "and reply with VALID JSON ONLY matching the schema exactly.")
    if nudge is None:
        return JSONResponse({"error": f"Model response failed validation 4 times (missing fields, wrong category/energy, safety/realism rule, or repeated verb). {first_err[:200]} Try again."}, status_code=502)

    entry_id = uuid.uuid4().hex[:12]
    result = {"title": nudge["title"], "task": nudge["task"], "why_it_fits": nudge["why_it_fits"],
              "bring": nudge["bring"], "minutes": nudge["minutes"],
              "energy": nudge["energy"], "category": nudge["category"],
              "weather": weather, "model": model, "part_of_day": pod, "local_time": time_str,
              "id": entry_id, "night": night,
              }
    save_history_entry({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "id": entry_id, "done": False,
        "mood": mood, "model": model, "title": nudge["title"], "task": nudge["task"],
        "category": nudge["category"], "energy": nudge["energy"],
    })
    return result

