"""
Translation of the application's own fixed text (message templates, labels,
interface strings) into the languages it is offered in.

What is translated is always text the application wrote. A person's details
are never sent anywhere: a message template is translated with its
placeholders protected ("{a} on the {doc_a}") and the values are filled in
afterwards, locally.

Sources, in order, per string:

1. a built-in catalog (hand-written, shipped with the code; Hindi for the
   finding messages - app/services/identity_messages.py);
2. the cache (this process, then Redis);
3. Google Cloud Translation, when GOOGLE_TRANSLATE_API_KEY is set.

A string none of them can supply comes back in English: a missing key, an
unreachable service or a mangled placeholder never fails a request.
"""
from __future__ import annotations

import hashlib
import html
import logging
import re
import time

import httpx

from app.core.config import settings

logger = logging.getLogger("fddt.translation")

SOURCE_LANGUAGE = "en"

# code -> (name in English, name in the language itself)
SUPPORTED_LANGUAGES: dict[str, tuple[str, str]] = {
    "en": ("English", "English"),
    "hi": ("Hindi", "हिन्दी"),
    "mr": ("Marathi", "मराठी"),
    "gu": ("Gujarati", "ગુજરાતી"),
    "bn": ("Bengali", "বাংলা"),
    "pa": ("Punjabi", "ਪੰਜਾਬੀ"),
    "ta": ("Tamil", "தமிழ்"),
    "te": ("Telugu", "తెలుగు"),
    "kn": ("Kannada", "ಕನ್ನಡ"),
    "ml": ("Malayalam", "മലയാളം"),
    "or": ("Odia", "ଓଡ଼ିଆ"),
    "as": ("Assamese", "অসমীয়া"),
    "ur": ("Urdu", "اردو"),
}
RIGHT_TO_LEFT = frozenset({"ur"})

# language -> {English text: translation}. Filled by the modules that own the
# text (see app/services/identity_messages.py).
BUILT_IN_CATALOGS: dict[str, dict[str, str]] = {}

_GOOGLE_URL = "https://translation.googleapis.com/language/translate/v2"
_GOOGLE_BATCH = 100
_CACHE_SECONDS = 30 * 24 * 3600
_PLACEHOLDER = re.compile(r"\{[a-z_]+\}")
_PROTECTED = re.compile(r"<span[^>]*>\s*(\{[a-z_]+\})\s*</span>")

# After a failed call Google is left alone for this long, so an outage costs
# one slow request and not one per page view.
_GOOGLE_RETRY_SECONDS = 60.0

_memory: dict[tuple[str, str], str] = {}
_google_paused_until = 0.0


def normalize_language(code: str | None) -> str:
    """A supported language code; anything else is English."""
    code = (code or "").strip().lower().split("-")[0]
    return code if code in SUPPORTED_LANGUAGES else SOURCE_LANGUAGE


def google_configured() -> bool:
    return bool(settings.google_translate_api_key)


def language_source(language: str) -> str:
    """Where a language's text comes from: "source" (English), "google",
    "built_in" (finding messages only, no key set) or "unavailable"."""
    if language == SOURCE_LANGUAGE:
        return "source"
    if google_configured():
        return "google"
    return "built_in" if language in BUILT_IN_CATALOGS else "unavailable"


def _cache_key(language: str, text: str) -> str:
    return f"fddt:i18n:{language}:{hashlib.sha1(text.encode('utf-8')).hexdigest()}"


def _redis():
    import redis

    return redis.Redis.from_url(settings.redis_url, socket_connect_timeout=0.3, socket_timeout=0.5)


def _from_redis(language: str, texts: list[str]) -> dict[str, str]:
    try:
        values = _redis().mget([_cache_key(language, t) for t in texts])
    except Exception:  # noqa: BLE001 - the cache is optional
        return {}
    return {t: v.decode("utf-8") for t, v in zip(texts, values) if v}


def _to_redis(language: str, translated: dict[str, str]) -> None:
    try:
        pipe = _redis().pipeline()
        for text, value in translated.items():
            pipe.set(_cache_key(language, text), value.encode("utf-8"), ex=_CACHE_SECONDS)
        pipe.execute()
    except Exception:  # noqa: BLE001
        pass


def _protect(text: str) -> str:
    return _PLACEHOLDER.sub(lambda m: f'<span translate="no">{m.group(0)}</span>', html.escape(text, quote=False))


def _restore(text: str) -> str:
    return html.unescape(_PROTECTED.sub(r"\1", text)).strip()


def _google(language: str, texts: list[str]) -> dict[str, str]:
    """Translations for `texts`; a string whose placeholders did not survive
    is left out (the caller then shows it in English)."""
    global _google_paused_until
    translated: dict[str, str] = {}
    if time.monotonic() < _google_paused_until:
        return translated
    for start in range(0, len(texts), _GOOGLE_BATCH):
        batch = texts[start : start + _GOOGLE_BATCH]
        try:
            response = httpx.post(
                _GOOGLE_URL,
                params={"key": settings.google_translate_api_key},
                json={
                    "q": [_protect(t) for t in batch],
                    "source": SOURCE_LANGUAGE,
                    "target": language,
                    "format": "html",
                },
                timeout=settings.google_translate_timeout_seconds,
            )
            response.raise_for_status()
            results = response.json()["data"]["translations"]
        except Exception:  # noqa: BLE001 - network, quota, bad key, bad payload
            logger.warning("Google Translation failed for %s (%d strings)", language, len(batch), exc_info=True)
            _google_paused_until = time.monotonic() + _GOOGLE_RETRY_SECONDS
            break
        for source, result in zip(batch, results):
            text = _restore(str(result.get("translatedText") or ""))
            if text and sorted(_PLACEHOLDER.findall(text)) == sorted(_PLACEHOLDER.findall(source)):
                translated[source] = text
    return translated


def translate(texts: list[str], language: str) -> list[str]:
    """`texts` (English) in `language`, in the same order. A string that
    cannot be translated is returned unchanged."""
    language = normalize_language(language)
    if language == SOURCE_LANGUAGE or not texts:
        return list(texts)

    built_in = BUILT_IN_CATALOGS.get(language, {})
    found: dict[str, str] = {}
    missing: list[str] = []
    for text in dict.fromkeys(texts):  # unique, in order
        if not text.strip():
            found[text] = text
        elif text in built_in:
            found[text] = built_in[text]
        elif (language, text) in _memory:
            found[text] = _memory[(language, text)]
        else:
            missing.append(text)

    if missing and google_configured():
        cached = _from_redis(language, missing)
        fresh = _google(language, [t for t in missing if t not in cached])
        if fresh:
            _to_redis(language, fresh)
        for text, value in {**cached, **fresh}.items():
            _memory[(language, text)] = value
            found[text] = value

    return [found.get(text, text) for text in texts]


def translate_one(text: str, language: str) -> str:
    return translate([text], language)[0]


def clear_memory_cache() -> None:
    """Forget this process's translations and any pause after a failure."""
    global _google_paused_until
    _memory.clear()
    _google_paused_until = 0.0
