"""Speech-to-text (English, Hindi, Telugu) using the Google Gemini API.

Setup (once):
  1. Create a Gemini API key at https://aistudio.google.com/ .
  2. Put it in the project's .env file as GEMINI_API_KEY=<your key>.
  Optionally set GEMINI_STT_MODEL in .env (default: gemini-2.5-flash).
"""

import base64
import json
import os
import urllib.error
import urllib.request

DEFAULT_MODEL = "gemini-2.5-flash"
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TIMEOUT_SECONDS = 60

LANG_NAMES = {"en": "English", "hi": "Hindi", "te": "Telugu"}


def transcribe(audio_bytes: bytes, language: str = "en") -> str:
    """Turn recorded audio into a transcript in the given language ("en", "hi" or "te")."""
    if not audio_bytes:
        raise RuntimeError("No audio was received. Please record again.")

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set. Add it to .env.")

    model = os.environ.get("GEMINI_STT_MODEL", "").strip() or DEFAULT_MODEL
    lang_key = (language or "en").strip().lower()
    lang_name = LANG_NAMES.get(lang_key, "English")

    prompt = (
        "Transcribe this audio exactly. The speaker uses "
        f"{lang_name}. Return only the transcript text in its original script, "
        "with no commentary."
    )
    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "audio/webm",
                            "data": base64.b64encode(audio_bytes).decode("ascii"),
                        }
                    },
                ]
            }
        ]
    }

    request = urllib.request.Request(
        API_URL.format(model=model),
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini request failed ({exc.code}): {detail[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Gemini request failed: {exc.reason}") from exc

    try:
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        error = payload.get("error") if isinstance(payload, dict) else None
        detail = f" Error: {error}" if error else ""
        raise RuntimeError(f"Gemini returned no transcript.{detail}") from None

    return str(text).strip()
