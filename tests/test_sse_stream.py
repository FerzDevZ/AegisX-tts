"""Unit test SSE streaming endpoint — docs/04 §4.3.

Kontrak:
- POST /v1/audio/speech/stream: text/event-stream, event meta/audio/done.
- Teks > batas → 413 sebelum stream dimulai.
- Bahasa tak didukung → 422.
- Server tanpa engine (bobot M2 belum ada) → 503; stream tidak pernah mulai.
- Streaming teruji via engine fixture eksplisit (bukan stub tersembunyi):
  fixture menghasilkan PCM16 sine nyata — jalur SSE produksi identik.
"""

from __future__ import annotations

import base64
import json
import math
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import numpy as np
from fastapi.testclient import TestClient

from aegisx_tts.constants import SAMPLE_RATE_HZ
from aegisx_tts.core.config import ModelConfig
from aegisx_tts.server.app import create_app

_CONFIG_PATH: Final[Path] = Path(__file__).parents[1] / "aegisx_tts" / "config" / "id.yaml"


class _SineEngine:
    """Engine fixture: PCM16 sine nyata per chunk (pengganti bobot M2)."""

    def synthesize_stream(
        self, text: str, language: str, voice: str
    ) -> Iterator[bytes]:
        _ = text, language, voice
        for i in range(3):
            t = (np.arange(SAMPLE_RATE_HZ // 10) + i * SAMPLE_RATE_HZ // 10) / SAMPLE_RATE_HZ
            wave = (0.3 * np.sin(2 * math.pi * 220.0 * t) * 32767).astype("<i2")
            yield wave.tobytes()


def _client(engine: object | None = None) -> TestClient:
    config = ModelConfig.from_yaml(_CONFIG_PATH)
    return TestClient(create_app(config, engine=engine))  # type: ignore[arg-type]


def _parse_events(text: str) -> list[dict[str, object]]:
    return [
        json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")
    ]


class TestSseStream:
    def test_content_type_event_stream(self) -> None:
        with _client(_SineEngine()) as client:
            resp = client.post(
                "/v1/audio/speech/stream",
                json={"text": "halo", "language": "id"},
            )
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")

    def test_event_format_seq_dan_done(self) -> None:
        with _client(_SineEngine()) as client:
            resp = client.post(
                "/v1/audio/speech/stream",
                json={"text": "halo dunia", "language": "id"},
            )
            payloads = _parse_events(resp.text)
            assert len(payloads) >= 3
            # seq monotonik mulai 0
            assert [p["seq"] for p in payloads] == list(range(len(payloads)))
            # event pertama meta, terakhir done
            assert payloads[0]["type"] == "meta"
            assert payloads[-1]["type"] == "done"
            assert payloads[-1]["done"] is True
            # event audio berisi base64 PCM yang didekode jadi sampel valid
            audio_events = [p for p in payloads if p["type"] == "audio"]
            assert len(audio_events) == 3
            for p in audio_events:
                raw = base64.b64decode(str(p["audio_b64"]))
                assert len(raw) > 0 and len(raw) % 2 == 0
            # tiap event punya kunci audio_b64 ("" untuk meta/done)
            for p in payloads:
                assert "audio_b64" in p

    def test_teks_terlalu_panjang_413_sebelum_stream(self) -> None:
        with _client() as client:
            resp = client.post(
                "/v1/audio/speech/stream",
                json={"text": "a" * 50_001, "language": "id"},
            )
            assert resp.status_code == 413

    def test_bahasa_tak_didukung_422(self) -> None:
        with _client() as client:
            resp = client.post(
                "/v1/audio/speech/stream",
                json={"text": "halo", "language": "fr"},
            )
            assert resp.status_code == 422

    def test_teks_kosong_422(self) -> None:
        with _client() as client:
            resp = client.post(
                "/v1/audio/speech/stream",
                json={"text": "   ", "language": "id"},
            )
            assert resp.status_code == 422

    def test_tanpa_engine_503_stream_tidak_dimulai(self) -> None:
        with _client() as client:
            resp = client.post(
                "/v1/audio/speech/stream",
                json={"text": "halo", "language": "id"},
            )
            assert resp.status_code == 503
            assert not resp.headers.get("content-type", "").startswith(
                "text/event-stream"
            )

    def test_voice_tak_dikenal_404(self) -> None:
        with _client(_SineEngine()) as client:
            resp = client.post(
                "/v1/audio/speech/stream",
                json={"text": "halo", "language": "id", "voice": "tak-ada"},
            )
            assert resp.status_code == 404
