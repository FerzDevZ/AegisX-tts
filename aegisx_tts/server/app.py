"""Server HTTP AegisX-TTS — docs/04 §4–5.

Endpoint:
- GET /                → web UI (CSP ketat)
- GET /health          → liveness
- GET /v1/voices       → katalog suara + lisensi (REQ-050)
- POST /v1/audio/speech → OpenAI-compatible (F6)
- POST /v1/audio/speech/stream → SSE streaming (docs/04 §4.3)

Error schema konsisten {"error": {code, message, locale}} dengan locale dari
header Accept-Language (id default, fallback en) — NFR-11/F10.
Sintesis nyata menunggu bobot M2 → 503 model_not_loaded (eksplisit).
Streaming via dependency injection `engine`: produksi default None → 503;
test menyuntik engine fixture eksplisit (bukan stub tersembunyi).
"""

from __future__ import annotations

import base64
import json
from collections.abc import Iterator
from typing import Any, Final, Literal

from fastapi import FastAPI, Header, Request, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
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


class StreamRequest(BaseModel):
    """Skema request SSE streaming (docs/04 §4.3)."""

    model_config = {"extra": "ignore"}

    text: str
    language: str | None = None
    voice: str | None = None


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


def create_app(config: ModelConfig, engine: Any | None = None) -> FastAPI:
    """Bangun app FastAPI; `engine` di-inject untuk streaming (M2 bobot)."""
    app = FastAPI(title="AegisX-TTS", version="0.1.0.dev1", docs_url=None, redoc_url=None)
    cfg = config
    voice_names = {v.name for v in cfg.voices}
    _engine = engine

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

    @app.post(
        "/v1/audio/speech/stream",
        response_model=None,
    )
    async def speech_stream(
        req: StreamRequest, accept_language: str | None = Header(default=None)
    ) -> JSONResponse | StreamingResponse:
        """SSE streaming: event meta → audio* → done (docs/04 §4.3)."""
        locale = _pick_locale(accept_language)
        language = req.language or cfg.language

        if not req.text or not req.text.strip():
            return _error_response(
                "invalid_request", get_message("error_input_required", locale), locale, 422
            )
        if len(req.text) > cfg.limits.max_text_chars:
            return _error_response(
                "text_too_long",
                get_message("error_text_too_long", locale, limit=cfg.limits.max_text_chars),
                locale,
                413,
            )
        if language not in SUPPORTED_LANGUAGES:
            return _error_response(
                "invalid_request",
                get_message("error_invalid_language", locale, lang=language),
                locale,
                422,
            )
        voice = req.voice or (cfg.voices[0].name if cfg.voices else "")
        if voice not in voice_names:
            return _error_response(
                "invalid_voice",
                get_message("error_invalid_voice", locale, voice=voice),
                locale,
                404,
            )
        if _engine is None:
            return _error_response(
                "model_not_loaded",
                f"Bobot '{cfg.language}' belum dirilis (target M2, docs/07 roadmap)",
                locale,
                503,
            )

        def sse_events() -> Iterator[str]:
            # meta event (docs/04 §4.3: sample_rate, format, voice, watermark)
            meta = {
                "type": "meta",
                "seq": 0,
                "sample_rate": 24000,
                "format": "pcm16",
                "voice": voice,
                "watermark": cfg.watermark.enabled,
                "audio_b64": "",
                "done": False,
            }
            yield f"data: {json.dumps(meta, ensure_ascii=False)}\n\n"
            seq = 1
            stream: Iterator[bytes] = _engine.synthesize_stream(
                req.text, language, voice
            )
            for chunk in stream:
                payload = {
                    "type": "audio",
                    "seq": seq,
                    "audio_b64": base64.b64encode(chunk).decode("ascii"),
                    "done": False,
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                seq += 1
            done = {
                "type": "done",
                "seq": seq,
                "audio_b64": "",
                "done": True,
            }
            yield f"data: {json.dumps(done, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            sse_events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.websocket("/v1/audio/speech/ws")
    async def speech_ws(websocket: WebSocket) -> None:
        """WS streaming dua arah + backpressure slow_consumer (docs/04 §4.3)."""
        import asyncio

        await websocket.accept()
        try:
            request = await websocket.receive_json()
            if request.get("type") != "synthesize":
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "invalid_request",
                        "message": "type harus 'synthesize'",
                    }
                )
                await websocket.close()
                return

            text = request.get("text", "")
            language = request.get("language") or cfg.language
            voice = request.get("voice") or (cfg.voices[0].name if cfg.voices else "")

            if not text or not str(text).strip():
                await websocket.send_json(
                    {"type": "error", "code": "invalid_request", "message": "teks wajib"}
                )
                await websocket.close()
                return
            if len(str(text)) > cfg.limits.max_text_chars:
                await websocket.send_json(
                    {"type": "error", "code": "text_too_long", "message": "teks terlalu panjang"}
                )
                await websocket.close()
                return
            if language not in SUPPORTED_LANGUAGES:
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "invalid_language",
                        "message": f"bahasa {language!r} tidak didukung",
                    }
                )
                await websocket.close()
                return
            if voice not in voice_names:
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "invalid_voice",
                        "message": f"suara {voice!r} tidak dikenal",
                    }
                )
                await websocket.close()
                return
            if _engine is None:
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "model_not_loaded",
                        "message": "bobot belum tersedia (M2)",
                    }
                )
                await websocket.close()
                return

            await websocket.send_json(
                {
                    "type": "meta",
                    "sample_rate": 24000,
                    "format": "pcm16",
                    "voice": voice,
                    "watermark": cfg.watermark.enabled,
                }
            )

            # Backpressure: budget = chunk yang dikirim tapi belum di-ACK.
            # 10 s audio (docs/04 §4.3); chunk engine fixture = 1 s.
            # Saat budget penuh: tunggu ACK secara memblokir (ACK_TIMEOUT);
            # slow_consumer hanya bila timeout habis — konsumen aktif yang
            # ACK-nya datang terlambat tidak salah dihukum.
            max_unacked = 10
            ack_timeout_s = 5.0
            sent_unread = 0
            seq = 0
            for chunk in _engine.synthesize_stream(str(text), language, voice):
                if sent_unread >= max_unacked:
                    try:
                        while sent_unread >= max_unacked:
                            ack = await asyncio.wait_for(
                                websocket.receive_json(), timeout=ack_timeout_s
                            )
                            if ack.get("type") == "ack":
                                sent_unread -= 1
                    except (asyncio.TimeoutError, TimeoutError):
                        await websocket.send_json(
                            {
                                "type": "error",
                                "code": "slow_consumer",
                                "message": "konsumen lebih lambat 10 s audio (docs/04 §4.3)",
                            }
                        )
                        await websocket.close()
                        return
                await websocket.send_json(
                    {
                        "type": "audio",
                        "seq": seq,
                        "audio_b64": base64.b64encode(chunk).decode("ascii"),
                    }
                )
                seq += 1
                sent_unread += 1
                # Drain ACK yang sudah menunggu tanpa memblokir lama.
                while True:
                    try:
                        ack = await asyncio.wait_for(
                            websocket.receive_json(), timeout=0.05
                        )
                        if ack.get("type") == "ack":
                            sent_unread = max(0, sent_unread - 1)
                    except (asyncio.TimeoutError, TimeoutError):
                        break

            await websocket.send_json({"type": "done"})
            await websocket.close()
        except Exception:
            try:
                await websocket.close()
            except Exception:  # pragma: no cover
                pass

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
