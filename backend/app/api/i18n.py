"""
Languages and translated text for the interface.

`GET /i18n/languages` lists the languages and whether each is available
right now. `GET /i18n/catalog` gives the labels the finding screens use
(fields, document types, severities, reasons) in one language. `POST
/i18n/translate` translates the frontend's own interface strings, so the
Google key stays on the server and each string is translated once and cached
(app/services/translation_service.py).

`/i18n/translate` is for fixed interface text. Do not send a person's
details through it: anything sent may go to Google Translation.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, StringConstraints

from app.api.auth import get_current_user
from app.models.user import User
from app.services import identity_messages as messages
from app.services.translation_service import (
    RIGHT_TO_LEFT,
    SUPPORTED_LANGUAGES,
    language_source,
    normalize_language,
    translate,
)

router = APIRouter(prefix="/i18n", tags=["i18n"])

MAX_TEXTS = 300
InterfaceText = Annotated[str, StringConstraints(max_length=500)]


class LanguageInfo(BaseModel):
    code: str
    name: str
    native_name: str
    direction: str = Field(description="`ltr` or `rtl`.")
    source: str = Field(
        description="`source` (English), `google` (everything can be translated), `built_in` (finding "
        "messages only; no Google key is set) or `unavailable` (falls back to English)."
    )
    available: bool


class TranslateRequest(BaseModel):
    language: str
    texts: list[InterfaceText] = Field(max_length=MAX_TEXTS)


class TranslateResponse(BaseModel):
    language: str
    translations: dict[str, str] = Field(description="English text -> text in `language`.")
    complete: bool = Field(description="False if any string came back in English.")


def _keyed(labels: dict[str, str], language: str) -> dict[str, str]:
    return dict(zip(labels, translate(list(labels.values()), language)))


@router.get("/languages", response_model=list[LanguageInfo], summary="Languages the interface is offered in")
def list_languages() -> list[LanguageInfo]:
    return [
        LanguageInfo(
            code=code,
            name=name,
            native_name=native,
            direction="rtl" if code in RIGHT_TO_LEFT else "ltr",
            source=language_source(code),
            available=language_source(code) != "unavailable",
        )
        for code, (name, native) in SUPPORTED_LANGUAGES.items()
    ]


@router.get(
    "/catalog",
    summary="Labels of the finding screens in one language",
    description=(
        "Field, document-type and severity labels plus the explanation and action text per reason, "
        "keyed by the same machine keys the case API returns (`field_name`, `document_type`, "
        "`severity`, `reason`)."
    ),
)
def catalog(lang: str = Query(default="en"), _: User = Depends(get_current_user)) -> dict:
    language = normalize_language(lang)
    return {
        "language": language,
        "direction": "rtl" if language in RIGHT_TO_LEFT else "ltr",
        "fields": _keyed(messages.FIELD_LABELS, language),
        "documents": _keyed(messages.DOCUMENT_LABELS, language),
        "severities": _keyed(messages.SEVERITY_LABELS, language),
        "reasons": _keyed({**messages.HARMLESS_REASONS, **messages.CONFLICT_REASONS}, language),
        "actions": _keyed(messages.ACTIONS, language),
        "no_action": translate([messages.NO_ACTION], language)[0],
    }


@router.post(
    "/translate",
    response_model=TranslateResponse,
    summary="Translate interface strings",
    description=(
        f"Up to {MAX_TEXTS} English strings of at most 500 characters each. For fixed interface text "
        "only; never send a person's details. A string that cannot be translated comes back in English."
    ),
)
def translate_interface(payload: TranslateRequest, _: User = Depends(get_current_user)) -> TranslateResponse:
    language = normalize_language(payload.language)
    texts = list(dict.fromkeys(payload.texts))
    translated = translate(texts, language)
    return TranslateResponse(
        language=language,
        translations=dict(zip(texts, translated)),
        complete=language == "en" or all(t != s or not s.strip() for s, t in zip(texts, translated)),
    )
