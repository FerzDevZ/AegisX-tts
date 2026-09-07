"""Unit test WebSocket streaming — docs/04 §4.3.

Kontrak:
- WS /v1/audio/speech/ws: klien kirim {"type":"synthesize", text, language},
  server balas {"type":"meta"}, lalu {"type":"audio"}*, lalu {"type":"done"}.
- Tanpa engine → server kirim {"type":"error"} code model_not_loaded lalu close.
- Bahasa tak didukung → error invalid_language.
- Backpressure: consumer yang tidak membaca melewati budget audio 10 s →
  server kirim error slow_consumer dan close (docs/04 §4.3).
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import numpy as np
import pytest
from fastapi.testclient import TestClient

from aegisx_tts.constants import SAMPLE_RATE_HZ
from aegisx_tts.core.config import ModelConfig
from aegisx_tts.server.app import create_app

_CONFIG_PATH: Final[Path] = Path(__file__).parents[1] / "aegisx_tts" / "config" / "id.yaml"


class _SineEngine:
    """Engine fixture: 100 chunk × 1 s sine (untuk uji backpressure)."""

    def synthesize_stream(
        self, text: str, language: str, voice: str
    ) -> Iterator[bytes]:
        _ = text, language, voice
        for i in range(100):
            t = (np.arange(SAMPLE_RATE_HZ) + i * SAMPLE_RATE_HZ) / SAMPLE_RATE_HZ
            wave = (0.3 * np.sin(2 * math.pi * 220.0 * t) * 32767).astype("<i2")
            yield wave.tobytes()


def _client(engine: object | None = None) -> TestClient:
    config = ModelConfig.from_yaml(_CONFIG_PATH)
    return TestClient(create_app(config, engine=engine))  # type: ignore[arg-type]


class TestWsStream:
    def test_meta_audio_done_urutan(self) -> None:
        with _client(_SineEngine()) as client, client.websocket_connect(
            "/v1/audio/speech/ws"
        ) as ws:
            ws.send_json({"type": "synthesize", "text": "halo", "language": "id"})
            meta = ws.receive_json()
            assert meta["type"] == "meta"
            assert meta["sample_rate"] == SAMPLE_RATE_HZ
            audio_count = 0
            while True:
                msg = ws.receive_json()
                if msg["type"] == "done":
                    break
                assert msg["type"] == "audio"
                audio_count += 1
                # Konsumen aktif mengirim ACK per chunk (protokol docs/04 §4.3).
                ws.send_json({"type": "ack", "seq": msg["seq"]})
                if audio_count > 200:  # pragma: no cover — guard loop
                    pytest.fail("done tidak pernah tiba")
            assert audio_count >= 1

    def test_tanpa_engine_error_model_not_loaded(self) -> None:
        with _client() as client, client.websocket_connect(
            "/v1/audio/speech/ws"
        ) as ws:
            ws.send_json({"type": "synthesize", "text": "halo", "language": "id"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["code"] == "model_not_loaded"

    def test_bahasa_tak_didukung_error(self) -> None:
        with _client(_SineEngine()) as client, client.websocket_connect(
            "/v1/audio/speech/ws"
        ) as ws:
            ws.send_json({"type": "synthesize", "text": "halo", "language": "fr"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["code"] == "invalid_language"

    def test_teks_kosong_error(self) -> None:
        with _client(_SineEngine()) as client, client.websocket_connect(
            "/v1/audio/speech/ws"
        ) as ws:
            ws.send_json({"type": "synthesize", "text": "   ", "language": "id"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["code"] == "invalid_request"

    def test_backpressure_slow_consumer(self) -> None:
        """Klien berhenti membaca → server kirim error slow_consumer lalu close."""
        with _client(_SineEngine()) as client, client.websocket_connect(
            "/v1/audio/speech/ws"
        ) as ws:
            ws.send_json({"type": "synthesize", "text": "halo", "language": "id"})
            meta = ws.receive_json()
            assert meta["type"] == "meta"
            # Baca 3 chunk lalu berhenti membaca — server harus mendeteksi
            # backpressure (queue melebihi budget) dan mengirim error.
            for _ in range(3):
                ws.receive_json()
            # Server-side budget kecil di test via env? Kontrak: 10 s audio.
            # Di sini kita verifikasi lewat perilaku: setelah berhenti membaca,
            # akhirnya datang error slow_consumer (server mengirim saat queue
            # penuh dan engine masih menghasilkan).
            while True:
                msg = ws.receive_json()
                if msg["type"] == "error":
                    assert msg["code"] == "slow_consumer"
                    break
                if msg["type"] == "done":  # pragma: no cover — gagal kontrak
                    pytest.fail("harusnya slow_consumer, bukan done")
