"""Bounded, server-side transcription through a configured Speaches service."""

from __future__ import annotations

import fcntl
import json
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

import requests
from django.conf import settings


MAX_AUDIO_BYTES = 4 * 1024 * 1024
MAX_RECORDING_SECONDS = 60
MAX_TRANSCRIPT_LENGTH = 8192
MAX_RESPONSE_BYTES = 65536
DEFAULT_MODEL = "Systran/faster-whisper-small"
TRANSCRIPTION_PROMPT = (
    "Inventory vocabulary: O-rings, silicone, batteries, magnets, DC motors, "
    "PNP and NPN transistors, MOSFETs, resistors, capacitors, inductors. "
    "Units: ohms, kiloohms, microfarads, nanofarads, microhenries."
)
AUDIO_TYPES = {
    "audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a",
    "audio/wav": "wav", "audio/x-wav": "wav", "audio/mpeg": "mp3",
}


class SpeechError(RuntimeError):
    """A public error which never includes upstream audio, credentials or bodies."""

    def __init__(self, message, status=502, code="speech_unavailable"):
        super().__init__(message)
        self.status = status
        self.code = code


def validate_config(payload):
    """One JSON setting keeps connection changes atomic."""
    if not isinstance(payload, dict) or set(payload) - {"url", "model"}:
        raise ValueError("Use speech URL and model only; Part Finder uses English")
    url = payload.get("url", "")
    model = payload.get("model", DEFAULT_MODEL)
    if not all(isinstance(value, str) for value in (url, model)):
        raise ValueError("Speech settings must be text")
    url, model = url.strip().rstrip("/"), model.strip()
    if url:
        parsed = urlsplit(url)
        if (len(url) > 500 or parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or any(char.isspace() or ord(char) < 32 for char in url)):
            raise ValueError("Speech URL must be an HTTP(S) service URL without credentials, query or fragment")
        try:
            parsed.port
        except ValueError as exc:
            raise ValueError("Speech URL has an invalid port") from exc
    if not model or len(model) > 200 or any(char.isspace() or ord(char) < 32 for char in model):
        raise ValueError("Enter a model ID, for example Systran/faster-whisper-small")
    return {"url": url, "model": model}


def get_config(plugin):
    raw = plugin.get_setting("SPEECH_CONFIG", backup_value="")
    try:
        payload = json.loads(raw) if raw else {}
        if isinstance(payload, dict):
            # Discard the retired stored option, including during a rolling restart.
            payload.pop("language", None)
        return validate_config(payload)
    except (ValueError, TypeError):
        # A broken speech setting must never prevent typed finding or locating.
        return validate_config({})


def save_config(plugin, payload):
    config = validate_config(payload)
    plugin.set_setting("SPEECH_CONFIG", json.dumps(config))
    return config


def speech_lock_path():
    return Path(settings.MEDIA_ROOT) / ".wled-locator-speech.lock"


@contextmanager
def transcription_slot():
    """One addon transcription at a time, independently of the hardware lock."""
    with speech_lock_path().open("a+b") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SpeechError("Another transcription is running. Try again shortly.", 503, "speech_busy") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def transcribe(plugin, audio, content_type):
    """Forward in-memory audio only; never save recordings or call inventory/WLED."""
    if content_type not in AUDIO_TYPES:
        raise SpeechError("Unsupported recording format. Try another browser.", 415, "speech_format")
    if not audio:
        raise SpeechError("The recording is empty. Record again.", 400, "speech_empty")
    if len(audio) > MAX_AUDIO_BYTES:
        raise SpeechError("The recording exceeds 4 MiB. Make a shorter recording.", 413, "speech_size")
    config = get_config(plugin)
    if not config["url"]:
        raise SpeechError("Configure the speech service in Plugin Configuration first.", 503, "speech_not_configured")
    base = config["url"].removesuffix("/v1")
    data = {"model": config["model"], "response_format": "json", "temperature": "0", "language": "en",
            "prompt": TRANSCRIPTION_PROMPT}
    try:
        with transcription_slot(), requests.Session() as session:
            # Keep local audio off environment-configured outbound HTTP proxies.
            session.trust_env = False
            with session.post(
                base + "/v1/audio/transcriptions", data=data,
                files={"file": ("recording." + AUDIO_TYPES[content_type], audio, content_type)},
                timeout=(3, 60), allow_redirects=False, stream=True,
            ) as response:
                if response.status_code != 200:
                    raise SpeechError("Speaches could not transcribe this recording. Check the service and installed model.")
                body = bytearray()
                for chunk in response.iter_content(8192):
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise SpeechError("The speech service returned an oversized response.")
                payload = json.loads(body)
                text = payload.get("text") if isinstance(payload, dict) else None
                if not isinstance(text, str) or len(text) > MAX_TRANSCRIPT_LENGTH:
                    raise SpeechError("The speech service returned an invalid transcript.")
                text = text.strip()
                if not text:
                    raise SpeechError("No speech was recognized. Try recording again.", 422, "speech_empty")
                return {"text": text}
    except requests.Timeout as exc:
        raise SpeechError("Transcription timed out. Try a shorter recording.", 504, "speech_timeout") from exc
    except requests.RequestException as exc:
        raise SpeechError("Cannot reach Speaches. Check the speech service connection.") from exc
    except (ValueError, UnicodeError) as exc:
        raise SpeechError("The speech service returned an invalid response.") from exc
