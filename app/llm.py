"""Thin wrapper around the local Ollama JSON chat client."""
import json

from .config import OLLAMA_HOST

def call_ollama_json(model: str, system: str, user: str) -> dict:
    try:
        import ollama
        client = ollama.Client(host=OLLAMA_HOST)
        resp = client.chat(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            format="json",
        )
    except ImportError:
        raise RuntimeError("The 'ollama' package is not installed. Run: pip install -r requirements.txt")
    except Exception as e:
        msg = str(e)
        low = msg.lower()
        if "refused" in low or "connect" in low or "failed to connect" in low:
            raise RuntimeError(
                f"Cannot reach Ollama at {OLLAMA_HOST}. Is Ollama running? Start with 'ollama serve' and run 'ollama pull {model}'."
            )
        if "not found" in low or "no such" in low or "404" in msg:
            raise RuntimeError(f"Ollama error: model '{model}' not found. Run: ollama pull {model}. Details: {msg[:300]}")
        raise RuntimeError(f"Ollama request failed: {msg[:500]}")
    try:
        content = resp["message"]["content"] if isinstance(resp, dict) else resp.message.content
    except Exception as e:
        raise RuntimeError(f"Unexpected Ollama response shape: {e} | raw={str(resp)[:400]}")
    try:
        return json.loads(content) if isinstance(content, str) else content
    except Exception:
        raise ValueError(f"Model returned malformed JSON: {str(content)[:500]}")
