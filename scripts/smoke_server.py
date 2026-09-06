"""Smoke test server sungguhan: bind port, request health/voices/413, matikan."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request


def main() -> None:
    import uvicorn

    from aegisx_tts.core.config import ModelConfig
    from aegisx_tts.server.app import create_app

    app = create_app(ModelConfig.from_yaml("aegisx_tts/config/id.yaml"))
    config = uvicorn.Config(app, host="127.0.0.1", port=8765, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(2.5)

    health = urllib.request.urlopen("http://127.0.0.1:8765/health").read()
    voices = urllib.request.urlopen("http://127.0.0.1:8765/v1/voices?language=id").read()

    req = urllib.request.Request(
        "http://127.0.0.1:8765/v1/audio/speech",
        data=json.dumps(
            {"model": "aegisx-tts-1", "input": "x" * 50_001, "voice": "siregar"}
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req)
    except urllib.error.HTTPError as exc:
        print("413 body:", exc.read().decode())

    print("health:", health.decode())
    print("voices:", voices.decode()[:140])
    server.should_exit = True
    thread.join(timeout=5)


if __name__ == "__main__":
    main()
