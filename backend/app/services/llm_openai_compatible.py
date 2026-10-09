"""
Document reading with any service that speaks the OpenAI chat-completions
API (`LLM_PROVIDER=openai_compatible`): Google Gemini, Groq, a local Ollama
model and others. For development and demonstrations without Azure OpenAI.

Uses plain JSON mode with an example of the reply's shape in the prompt,
because strict JSON-schema output is not offered by every such service. The
reply is then repaired where a weaker model commonly slips (a missing key, a
bare string where an object was asked for, a date left as printed) and
validated against the same models the Azure service returns.

Text only: the checks that look at page images (visual review, signature
detection and comparison) are not available with this provider. Identity
bundles do not use them.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime
from typing import Any

from app.services.llm_service import (
    MAX_TOKENS_CLASSIFICATION,
    MAX_TOKENS_ENTITY_MATCH,
    MAX_TOKENS_SIGNATURE_COMPARISON,
    MAX_TOKENS_SIGNATURE_DETECTION,
    MAX_TOKENS_VISUAL_REVIEW,
    DocumentAnalysis,
    EntityMatchJudgment,
    IdentityAnalysis,
    LLMConfigurationError,
    LLMOperationError,
    LLMService,
    PageSignatureDetection,
    PageVisualAnalysis,
    SignatureComparisonResult,
    _analysis_json_schema,
    _entity_match_json_schema,
    _identity_json_schema,
    _page_visual_analysis_json_schema,
    _signature_comparison_json_schema,
    _signature_detection_json_schema,
    _ENTITY_MATCH_SYSTEM_PROMPT,
    _IDENTITY_SYSTEM_PROMPT_TEMPLATE,
    _SIGNATURE_COMPARISON_SYSTEM_PROMPT,
    _SIGNATURE_DETECTION_SYSTEM_PROMPT,
    _SYSTEM_PROMPT_TEMPLATE,
    _VISUAL_INCONSISTENCY_SYSTEM_PROMPT,
)

_JSON_INSTRUCTION = (
    "\n\nReply with ONE JSON object and nothing else: no explanation, no code fence. "
    "Use exactly this shape and these keys, replacing each placeholder with the real value "
    "(null where the document does not state it):\n"
)
_NO_VISION = "The configured LLM provider reads text only; checks that look at page images are not available."


def _types(schema: dict[str, Any]) -> list[str]:
    declared = schema.get("type")
    return declared if isinstance(declared, list) else [declared]


def _skeleton(schema: dict[str, Any]) -> Any:
    """An example of the reply's shape. Smaller models follow an example
    reliably, where a JSON schema makes some of them echo the schema."""
    types = _types(schema)
    if "object" in types:
        return {key: _skeleton(sub) for key, sub in schema.get("properties", {}).items()}
    if "array" in types:
        return [_skeleton(schema.get("items", {}))]
    kind = next((t for t in types if t != "null"), "string")
    return f"<{kind}{' or null' if 'null' in types else ''}>"


def _repair(schema: dict[str, Any], data: Any) -> Any:
    """`data` shaped to `schema`: missing keys filled in, a bare value
    wrapped into the field object it belongs to. Values are never invented."""
    types = _types(schema)
    if "object" in types:
        properties = schema.get("properties", {})
        if not isinstance(data, dict):
            data = {"value": data} if "value" in properties else {}
        out = {key: _repair(sub, data.get(key)) for key, sub in properties.items()}
        if "value" in properties:
            present = out["value"] not in (None, "")
            if "confidence" in properties and not isinstance(data.get("confidence"), (int, float)):
                out["confidence"] = 0.9 if present else 0.0
            if "uncertain" in properties and not isinstance(data.get("uncertain"), bool):
                out["uncertain"] = not present
            if "latin" in properties and out.get("latin") is None and isinstance(out["value"], str) and out["value"].isascii():
                out["latin"] = out["value"]
        return out
    if "array" in types:
        return [_repair(schema.get("items", {}), item) for item in data] if isinstance(data, list) else []
    if data is None:
        if "null" in types:
            return None
        return {"number": 0.0, "boolean": False, "string": ""}.get(types[0])
    if "number" in types and isinstance(data, str):
        try:
            return float(data.replace(",", ""))
        except ValueError:
            return None if "null" in types else 0.0
    if "string" in types and not isinstance(data, str) and "number" not in types:
        return str(data)
    return data


_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %B %Y", "%d %b %Y", "%d-%b-%Y", "%d-%B-%Y",
                 "%B %d, %Y", "%b %d, %Y", "%Y/%m/%d")
_GENDERS = {
    "m": "male", "male": "male", "पुरुष": "male",
    "f": "female", "female": "female", "महिला": "female", "स्त्री": "female",
    "other": "other", "transgender": "other", "अन्य": "other",
}
_POSTAL_CODE = re.compile(r"(?<!\d)\d{6}(?!\d)")


def _iso_date(*candidates: Any) -> str | None:
    """The first candidate that is a date, as YYYY-MM-DD. Day comes before
    month in a numeric date, as on Indian documents."""
    for candidate in candidates:
        text = " ".join(str(candidate or "").split())
        for pattern in _DATE_FORMATS:
            try:
                return datetime.strptime(text, pattern).date().isoformat()
            except ValueError:
                continue
    return None


def _normalise_identity(parsed: dict[str, Any]) -> dict[str, Any]:
    """Representation only, for models that copy a value as printed where
    the prompt asks for a normal form. Nothing is added that the reply did
    not contain."""
    for name in ("date_of_birth", "issue_date"):
        field = parsed.get(name) or {}
        if field.get("value") or field.get("raw_text"):
            field["raw_text"] = field.get("raw_text") or field.get("value")
            field["value"] = _iso_date(field.get("value"), field.get("raw_text"))

    gender = parsed.get("gender") or {}
    for candidate in (gender.get("value"), gender.get("raw_text")):
        key = str(candidate or "").strip().casefold()
        if key in _GENDERS:
            gender["raw_text"] = gender.get("raw_text") or candidate
            gender["value"] = _GENDERS[key]
            break
    else:
        gender["value"] = None

    income = parsed.get("annual_income") or {}
    if income.get("value") is None and income.get("raw_text"):
        digits = re.sub(r"[^\d.]", "", str(income["raw_text"]).split("/")[0]).strip(".")
        if digits and digits.count(".") <= 1:
            income["value"] = float(digits)

    address = parsed.get("address") or {}
    if not address.get("postal_code"):
        found = _POSTAL_CODE.search(f"{address.get('value') or ''} {address.get('latin') or ''}")
        address["postal_code"] = found.group(0) if found else None
    return parsed


_RATE_LIMIT_ATTEMPTS = 6
_MAX_WAIT_SECONDS = 60.0


def _retry_after_seconds(exc: Exception, attempt: int) -> float:
    """How long the service asked us to wait, else 5, 10, 20... seconds."""
    headers = getattr(getattr(exc, "response", None), "headers", None) or {}
    try:
        wait = float(headers.get("retry-after"))
    except (TypeError, ValueError):
        found = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", str(exc))
        wait = (int(found.group(1) or 0) * 60 + float(found.group(2))) if found else 5.0 * 2 ** attempt
    return min(max(wait, 1.0) + 0.5, _MAX_WAIT_SECONDS)


class OpenAICompatibleLLMService(LLMService):
    def __init__(
        self,
        base_url: str | None,
        api_key: str | None,
        model: str | None,
        timeout_seconds: float,
        vision_base_url: str | None = None,
        vision_api_key: str | None = None,
        vision_model: str | None = None,
    ):
        if not base_url or not model:
            raise LLMConfigurationError(
                "LLM_BASE_URL and LLM_MODEL must be set in backend/.env for LLM_PROVIDER=openai_compatible "
                "(see .env.example)."
            )
        from openai import OpenAI

        self._model = model
        self._client = OpenAI(
            base_url=base_url, api_key=api_key or "not-needed", timeout=timeout_seconds, max_retries=0
        )
        # Dedicated Vision model (e.g. Gemini Vision for images while Groq processes text)
        self._vision_model = vision_model or model
        if vision_base_url:
            self._vision_client = OpenAI(
                base_url=vision_base_url,
                api_key=vision_api_key or "not-needed",
                timeout=timeout_seconds,
                max_retries=0,
            )
        else:
            self._vision_client = self._client

    def _chat_json(
        self,
        system_prompt: str,
        user_content: str | list[dict[str, Any]],
        schema: dict[str, Any],
        max_tokens: int,
        temperature: float = 0,
        use_vision_client: bool = False,
    ) -> dict[str, Any]:
        from openai import APIError, RateLimitError

        client = self._vision_client if use_vision_client else self._client
        model = self._vision_model if use_vision_client else self._model

        messages = [
            {"role": "system", "content": system_prompt + _JSON_INSTRUCTION
             + json.dumps(_skeleton(schema), ensure_ascii=False, indent=1)},
            {"role": "user", "content": user_content},
        ]
        for attempt in range(_RATE_LIMIT_ATTEMPTS):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                break
            except RateLimitError as exc:
                if attempt == _RATE_LIMIT_ATTEMPTS - 1:
                    raise LLMOperationError(f"LLM request failed: {exc}") from exc
                time.sleep(_retry_after_seconds(exc, attempt))
            except APIError as exc:
                if (getattr(exc, "status_code", None) in (503, 500, 502) or "temporar" in str(exc).lower() or "high demand" in str(exc).lower()) and attempt < _RATE_LIMIT_ATTEMPTS - 1:
                    time.sleep(2.0 * (attempt + 1))
                    continue
                raise LLMOperationError(f"LLM request failed: {exc}") from exc
        content = (response.choices[0].message.content or "").strip()
        if content.startswith("```"):
            content = content.strip("`").removeprefix("json").strip()
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMOperationError(f"The LLM did not return valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise LLMOperationError("The LLM did not return a JSON object.")
        if isinstance(parsed.get("properties"), dict) and not set(parsed) & set(schema.get("properties", {})):
            parsed = parsed["properties"]
        return _repair(schema, parsed)

    def classify_and_extract(self, document_text: str, document_type_labels: list[str]) -> DocumentAnalysis:
        parsed = self._chat_json(
            _SYSTEM_PROMPT_TEMPLATE.format(labels=", ".join(document_type_labels)),
            document_text, _analysis_json_schema(), MAX_TOKENS_CLASSIFICATION,
        )
        try:
            return DocumentAnalysis.model_validate(parsed)
        except ValueError as exc:
            raise LLMOperationError(f"The LLM reply did not match the expected shape: {exc}") from exc

    def extract_identity(self, document_text: str, document_type_labels: list[str]) -> IdentityAnalysis:
        parsed = self._chat_json(
            _IDENTITY_SYSTEM_PROMPT_TEMPLATE.format(labels=", ".join(document_type_labels)),
            document_text, _identity_json_schema(), MAX_TOKENS_CLASSIFICATION,
        )
        try:
            return IdentityAnalysis.model_validate(_normalise_identity(parsed))
        except ValueError as exc:
            raise LLMOperationError(f"The LLM reply did not match the expected shape: {exc}") from exc

    def judge_entity_match(self, name: str, candidates: list[str]) -> EntityMatchJudgment:
        if not candidates:
            return EntityMatchJudgment(matched_candidate=None, reasoning="No candidates to compare.")
        parsed = self._chat_json(
            _ENTITY_MATCH_SYSTEM_PROMPT,
            json.dumps({"name": name, "candidates": candidates}, ensure_ascii=False),
            _entity_match_json_schema(), MAX_TOKENS_ENTITY_MATCH,
        )
        if parsed.get("matched_candidate") not in candidates:
            parsed["matched_candidate"] = None
        return EntityMatchJudgment.model_validate(parsed)

    def analyze_page_visual_consistency(self, image_data_uri: str) -> PageVisualAnalysis:
        parsed = self._chat_json(
            _VISUAL_INCONSISTENCY_SYSTEM_PROMPT,
            [
                {"type": "text", "text": "Analyze this document page image per the instructions."},
                {"type": "image_url", "image_url": {"url": image_data_uri, "detail": "high"}},
            ],
            _page_visual_analysis_json_schema(),
            max_tokens=2048,
            temperature=0.4,
            use_vision_client=True,
        )
        try:
            return PageVisualAnalysis.model_validate(parsed)
        except ValueError as exc:
            raise LLMOperationError(f"The LLM reply did not match the expected shape: {exc}") from exc

    def compare_signatures(self, ref_image_data_uri: str, target_image_data_uri: str) -> SignatureComparisonResult:
        parsed = self._chat_json(
            _SIGNATURE_COMPARISON_SYSTEM_PROMPT,
            [
                {"type": "text", "text": "Compare these two signature/stamp images and return your assessment."},
                {"type": "image_url", "image_url": {"url": ref_image_data_uri, "detail": "high"}},
                {"type": "image_url", "image_url": {"url": target_image_data_uri, "detail": "high"}},
            ],
            _signature_comparison_json_schema(),
            max_tokens=1024,
            temperature=0,
            use_vision_client=True,
        )
        try:
            return SignatureComparisonResult.model_validate(parsed)
        except ValueError as exc:
            raise LLMOperationError(f"The LLM reply did not match the expected shape: {exc}") from exc

    def detect_signatures_stamps(self, image_data_uri: str) -> PageSignatureDetection:
        parsed = self._chat_json(
            _SIGNATURE_DETECTION_SYSTEM_PROMPT,
            [
                {"type": "text", "text": "Locate any signature or stamp on this page."},
                {"type": "image_url", "image_url": {"url": image_data_uri, "detail": "high"}},
            ],
            _signature_detection_json_schema(),
            max_tokens=2048,
            temperature=0,
            use_vision_client=True,
        )
        try:
            return PageSignatureDetection.model_validate(parsed)
        except ValueError as exc:
            raise LLMOperationError(f"The LLM reply did not match the expected shape: {exc}") from exc
