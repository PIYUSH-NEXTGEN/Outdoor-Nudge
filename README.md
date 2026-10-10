# Outdoor Nudge

A small, local-first app that suggests **one concrete outdoor micro-mission**
based on your mood and the current weather — powered by a **local LLM (Ollama)**
and **Open-Meteo** weather. No paid APIs, no cloud accounts.

> _Full documentation coming soon._

## Quick start

```bash
# 1. Install dependencies
python -m venv venv
.\venv\Scripts\activate        # Windows
pip install -r requirements.txt

# 2. Make sure Ollama is running and a chat model is pulled
ollama serve
ollama pull llama3.2:3b

# 3. Run the API
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000> in your browser.

## Configuration

All settings can be overridden with environment variables (see `.env.example`).
Defaults work out of the box:

| Variable                  | Default             | Purpose                            |
|---------------------------|---------------------|------------------------------------|
| `OLLAMA_HOST`             | `http://localhost:11434` | Local Ollama server URL       |
| `NUDGE_MODEL`             | `llama3.2:3b`       | Default chat model                 |
| `NUDGE_LAT` / `NUDGE_LON` | `44.4268` / `26.1025` | Location for weather lookup      |
| `NUDGE_WEATHER_TIMEOUT`   | `12`                | Open-Meteo timeout (seconds)       |
| `NUDGE_HISTORY_FILE`      | `data/history.json` | Where history is saved (private!)  |
| `NUDGE_INDEX_FILE`        | `static/index.html` | Front-end served at `/`            |

## Project layout

```
app/            backend (FastAPI routes, config, prompts, validation, weather, llm, history)
static/         index.html (front-end)
tests/          safety unit tests, safety retest, Playwright browser tests
docs/           screenshots + docs
data/           history.json (auto-created, gitignored - contains private moods)
```

## Tests

```bash
.\venv\Scripts\python.exe tests\test_safety_unit.py     # offline validator checks
.\venv\Scripts\python.exe tests\test_safety_fixes.py    # live LLM safety retest (needs server + Ollama)
.\venv\Scripts\python.exe tests\test_browser.py         # Playwright UI tests (needs server)
```

## License

MIT — see [LICENSE](LICENSE).
