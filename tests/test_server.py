"""Unit test server HTTP (docs/04 §4–5).

Kontrak yang dijamin:
- GET /health → 200 tanpa auth.
- GET /v1/voices → katalog dari ModelConfig + metadata lisensi.
- POST /v1/audio/speech (OpenAI-compatible):
  * tanpa `input` → 422, error schema locale-aware (AC-5)
  * teks > max_text_chars → 413 text_too_long (AC-8/T4)
  * voice tak dikenal → 404 invalid_voice
  * response_format tak dikenal → 422
  * bobot belum tersedia → 503 model_not_loaded (eksplisit, bukan 500)
- Error schema konsisten: {"error": {code, message, locale}}.
- Web UI GET / hadir dengan CSP header (docs/04 §4.5).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from aegisx_tts.core.config import parse_config_dict
from aegisx_tts.server.app import create_app

CONFIG: dict[str, object] = {
    "schema_version": 1,
    "model": {
        "backbone": {"layers": 12, "d_model": 768, "heads": 12, "d_ff": 2560},
        "codec": {"sample_rate": 24000, "frame_ms": 80, "rvq_levels": 8, "codebook_size": 1024},
    },
    "language": "id",
    "voices": [
        {"name": "siregar", "file": "voices/siregar.safetensors", "license": "CC-BY-4.0"},
        {"name": "kartini", "file": "voices/kartini.safetensors", "license": "CC0-1.0"},
    ],
    "limits": {"max_text_chars": 50000},
}


def _client() -> TestClient:
    cfg = parse_config_dict(CONFIG)
    return TestClient(create_app(cfg))


class TestHealth:
    def test_health_ok(self) -> None:
        with _client() as client:
            res = client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


class TestVoices:
    def test_daftar_suara(self) -> None:
        with _client() as client:
            res = client.get("/v1/voices", params={"language": "id"})
        assert res.status_code == 200
        names = [v["name"] for v in res.json()["voices"]]
        assert names == ["siregar", "kartini"]
        assert res.json()["voices"][0]["license"] == "CC-BY-4.0"


class TestSpeechEndpoint:
    def test_tanpa_input_422(self) -> None:
        with _client() as client:
            res = client.post(
                "/v1/audio/speech", json={"model": "aegisx-tts-1", "voice": "siregar"}
            )
        assert res.status_code == 422
        err = res.json()["error"]
        assert err["code"] == "invalid_request"

    def test_teks_terlalu_panjang_413(self) -> None:
        with _client() as client:
            res = client.post(
                "/v1/audio/speech",
                json={"model": "aegisx-tts-1", "input": "a" * 50_001, "voice": "siregar"},
            )
        assert res.status_code == 413
        assert res.json()["error"]["code"] == "text_too_long"

    def test_voice_tak_kenal_404(self) -> None:
        with _client() as client:
            res = client.post(
                "/v1/audio/speech",
                json={"model": "aegisx-tts-1", "input": "halo", "voice": "hantu"},
            )
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "invalid_voice"

    def test_response_format_asal_422(self) -> None:
        with _client() as client:
            res = client.post(
                "/v1/audio/speech",
                json={
                    "model": "aegisx-tts-1",
                    "input": "halo",
                    "voice": "siregar",
                    "response_format": "flac",
                },
            )
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "invalid_request"

    def test_bobot_belum_rilis_503_eksplisit(self) -> None:
        with _client() as client:
            res = client.post(
                "/v1/audio/speech",
                json={"model": "aegisx-tts-1", "input": "halo", "voice": "siregar"},
            )
        assert res.status_code == 503
        assert res.json()["error"]["code"] == "model_not_loaded"

    def test_error_locale_en(self) -> None:
        with _client() as client:
            res = client.post(
                "/v1/audio/speech",
                json={"model": "aegisx-tts-1", "input": "a" * 50_001, "voice": "siregar"},
                headers={"Accept-Language": "en"},
            )
        assert res.json()["error"]["locale"] == "en"

    def test_error_locale_default_id(self) -> None:
        with _client() as client:
            res = client.post(
                "/v1/audio/speech",
                json={"model": "aegisx-tts-1", "input": "a" * 50_001, "voice": "siregar"},
            )
        assert res.json()["error"]["locale"] == "id"


class TestWebUI:
    def test_root_dengan_csp(self) -> None:
        with _client() as client:
            res = client.get("/")
        assert res.status_code == 200
        assert "default-src 'self'" in res.headers["content-security-policy"]
        assert "AegisX" in res.text
