"""Smoke test server streaming: SSE + WS di port asli (bukan mock)."""

from __future__ import annotations

import json
import math
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import uvicorn

sys.path.insert(0, str(Path(__file__).parents[1]))

from aegisx_tts.constants import SAMPLE_RATE_HZ  # noqa: E402
from aegisx_tts.core.config import ModelConfig  # noqa: E402
from aegisx_tts.server.app import create_app  # noqa: E402


class _SineEngine:
    def synthesize_stream(
        self, text: str, language: str, voice: str
    ) -> Iterator[bytes]:
        _ = text, language, voice
        for i in range(3):
            t = (np.arange(SAMPLE_RATE_HZ // 4) + i * SAMPLE_RATE_HZ // 4) / SAMPLE_RATE_HZ
            yield (0.3 * np.sin(2 * math.pi * 220.0 * t) * 32767).astype("<i2").tobytes()


def main() -> int:
    config = ModelConfig.from_yaml(
        Path(__file__).parents[1] / "aegisx_tts" / "config" / "id.yaml"
    )
    app = create_app(config, engine=_SineEngine())

    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=8901, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        print("FAIL: server tidak start")
        return 1

    import httpx

    base = "http://127.0.0.1:8901"
    with httpx.Client(base_url=base, timeout=10.0) as client:
        # Health
        r = client.get("/health")
        print("health:", r.json())

        # SSE streaming
        with client.stream(
            "POST",
            "/v1/audio/speech/stream",
            json={"text": "Halo dunia", "language": "id"},
        ) as resp:
            assert resp.status_code == 200, resp.status_code
            ctype = resp.headers.get("content-type", "")
            assert ctype.startswith("text/event-stream"), ctype
            types: list[str] = []
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    types.append(json.loads(line[6:])["type"])
            print("SSE event types:", types)
            assert types[0] == "meta" and types[-1] == "done"

        # Error path tetap terjaga
        r = client.post(
            "/v1/audio/speech/stream", json={"text": "a" * 50_001, "language": "id"}
        )
        print("SSE 413:", r.status_code, r.json()["error"]["code"])
        assert r.status_code == 413

    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
