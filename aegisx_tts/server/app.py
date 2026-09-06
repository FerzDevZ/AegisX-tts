"""Server HTTP AegisX-TTS — docs/04 §4–5.

Endpoint:
- GET /                → web UI (CSP ketat)
- GET /health          → liveness
- GET /v1/voices       → katalog suara + lisensi (REQ-050)
- POST /v1/audio/speech → OpenAI-compatible (F6)

Error schema konsisten {"error": {code, message, locale}} dengan locale dari
header Accept-Language (id default, fallback en) — NFR-11/F10.
Sintesis nyata menunggu bobot M2 → 503 model_not_loaded (eksplisit).
"""

from __future__ import annotations

from typing import Any, Final, Literal

from fastapi import FastAPI, Header, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from aegisx_tts.constants import SUPPORTED_LANGUAGES
from aegisx_tts.core.config import ModelConfig
from aegisx_tts.errors import ModelWeightsUnavailable
from aegisx_tts.i18n.messages import get_message

AllowedFormat = Literal["wav", "pcm", "mp3", "opus"]

_FORMATS: Final[frozenset[str]] = frozenset({"wav", "pcm", "mp3", "opus"})


class SpeechRequest(BaseModel):
    """Skema request OpenAI-compatible + field bahasa (docs/04 §4.2)."""

    model_config = {"extra": "ignore"}

    model: str
    input: str | None = None
    voice: str
    language: str | None = None
    response_format: str = "wav"


class SpeechResponse(BaseModel):
    """Error schema konsisten semua endpoint (docs/04 §5)."""

    error: dict[str, str]


def _pick_locale(accept_language: str | None) -> str:
    if not accept_language:
        return "id"
    first = accept_language.split(",")[0].strip().lower()
    code = first.split("-")[0]
    return code if code in SUPPORTED_LANGUAGES else "id"


def _error_response(code: str, message: str, locale: str, status: int) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "locale": locale}},
    )


def create_app(config: ModelConfig) -> FastAPI:
    app = FastAPI(title="AegisX-TTS", version="0.1.0.dev1", docs_url=None, redoc_url=None)
    cfg = config
    voice_names = {v.name for v in cfg.voices}

    @app.middleware("http")
    async def csp_header(request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        return response

    @app.get("/")
    async def root() -> HTMLResponse:
        return HTMLResponse(_render_ui())

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/voices")
    async def voices(language: str = cfg.language) -> JSONResponse:
        items = [
            {"name": v.name, "language": cfg.language, "license": v.license, "file": v.file}
            for v in cfg.voices
        ]
        _ = language
        return JSONResponse(content={"voices": items})

    @app.post("/v1/audio/speech")
    async def speech(
        req: SpeechRequest, accept_language: str | None = Header(default=None)
    ) -> JSONResponse:
        locale = _pick_locale(accept_language)

        if not req.input or not req.input.strip():
            return _error_response(
                "invalid_request", get_message("error_input_required", locale), locale, 422
            )
        if len(req.input) > cfg.limits.max_text_chars:
            return _error_response(
                "text_too_long",
                get_message("error_text_too_long", locale, limit=cfg.limits.max_text_chars),
                locale,
                413,
            )
        if req.voice not in voice_names:
            return _error_response(
                "invalid_voice",
                get_message("error_invalid_voice", locale, voice=req.voice),
                locale,
                404,
            )
        if req.response_format not in _FORMATS:
            return _error_response(
                "invalid_request",
                get_message("error_invalid_format", locale, fmt=req.response_format),
                locale,
                422,
            )

        # Semua validasi lolos → sintesis membutuhkan bobot (M2 docs/07).
        try:
            raise ModelWeightsUnavailable(
                f"Bobot '{cfg.language}' belum dirilis (target M2, docs/07 roadmap)"
            )
        except ModelWeightsUnavailable as exc:
            return _error_response("model_not_loaded", str(exc), locale, 503)

    def _render_ui() -> str:
        voice_options = "".join(
            f'<option value="{v.name}">{v.name}</option>' for v in cfg.voices
        )
        return (
            "<!DOCTYPE html><html lang='id'><head><meta charset='utf-8'>"
            "<title>AegisX-TTS</title></head><body>"
            "<h1>AegisX-TTS</h1><p>CPU-first streaming TTS (id, en, ms, jv).</p>"
            f"<form method='post' action='/v1/audio/speech'>"
            f"<select name='voice'>{voice_options}</select> "
            "<textarea name='input' rows='4' cols='50' placeholder='Tulis teks…'></textarea> "
            "<button type='submit'>Bicara</button></form>"
            "<p><a href='/health'>health</a></p></body></html>"
        )

    _ = SpeechResponse  # kontrak eksplisit; dipakai penuh saat M2 wiring
    return app
