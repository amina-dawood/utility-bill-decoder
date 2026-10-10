"""One thin wrapper around the model API (OpenAI only)."""
import base64
import json
import re
import time
from pathlib import Path

import config

_client = None


def _get_client():
    global _client
    if _client is None:
        if config.MODEL_PROVIDER != "openai":
            raise RuntimeError("This solution supports MODEL_PROVIDER=openai only.")
        if not config.API_KEY:
            raise RuntimeError("API_KEY is missing. Copy .env.example to .env and fill it in.")
        from openai import OpenAI
        _client = OpenAI(api_key=config.API_KEY)
    return _client


def text_part(text):
    return {"type": "text", "text": text}


def image_part(path):
    path = Path(path)
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    b64 = base64.b64encode(path.read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"}}


def _parse_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise


def chat_json(messages, retries=3):
    """Send messages, return a parsed JSON object. Retries on API or parse errors."""
    last = None
    for attempt in range(retries):
        try:
            kwargs = {}
            if config.MODEL_NAME.startswith("gpt-4"):
                kwargs["temperature"] = 0
            resp = _get_client().chat.completions.create(
                model=config.MODEL_NAME,
                messages=messages,
                response_format={"type": "json_object"},
                **kwargs,
            )
            return _parse_json(resp.choices[0].message.content or "")
        except Exception as e:  # network, rate limit, bad JSON
            last = e
            print(f"  [retry {attempt + 1}/{retries}] {type(e).__name__}: {str(e)[:120]}")
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Model call failed after {retries} tries: {last}")
