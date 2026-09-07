"""Unit test WAV IO + CLI verify watermark — docs/05 §3, docs/04 §2."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import torch
from typer.testing import CliRunner

from aegisx_tts.cli.main import app
from aegisx_tts.constants import SAMPLE_RATE_HZ
from aegisx_tts.core.watermark import WmkPayload, embed_watermark

runner = CliRunner()


def _pcm16_bytes(audio: torch.Tensor) -> bytes:
    """Tensor float [-1,1] → bytes PCM 16-bit little-endian."""
    ints = (audio.clamp(-1.0, 1.0) * 32767.0).to(torch.int16)
    return ints.numpy().tobytes()


def _read_wav(path: Path) -> torch.Tensor:
    with wave.open(str(path), "rb") as w:
        assert w.getframerate() == SAMPLE_RATE_HZ
        assert w.getnchannels() == 1
        raw = w.readframes(w.getnframes())
    ints = np.frombuffer(raw, dtype="<i2")
    return torch.from_numpy(ints.astype(np.float32) / 32768.0)


def _write_wav(tmp_path: Path, audio: torch.Tensor, name: str = "a.wav") -> Path:
    path = tmp_path / name
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE_HZ)
        w.writeframes(_pcm16_bytes(audio))
    return path


class TestCliVerify:
    def test_verify_wav_berwatermark(self, tmp_path: Path) -> None:
        payload = WmkPayload(tier="written", voice="siregar")
        marked = embed_watermark(
            0.5 * torch.sin(2 * np.pi * 220.0 * torch.arange(SAMPLE_RATE_HZ * 2) / SAMPLE_RATE_HZ),
            payload,
        )
        path = _write_wav(tmp_path, marked)
        result = runner.invoke(app, ["verify", str(path)])
        assert result.exit_code == 0, result.output
        assert '"tier": "written"' in result.output
        assert '"voice": "siregar"' in result.output

    def test_verify_wav_tanpa_watermark(self, tmp_path: Path) -> None:
        clean = 0.5 * torch.sin(
            2 * np.pi * 220.0 * torch.arange(SAMPLE_RATE_HZ * 2) / SAMPLE_RATE_HZ
        )
        path = _write_wav(tmp_path, clean)
        result = runner.invoke(app, ["verify", str(path)])
        assert result.exit_code == 1
        assert "watermark" in result.output.lower()

    def test_verify_file_tidak_ada(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["verify", str(tmp_path / "missing.wav")])
        assert result.exit_code == 1

    def test_verify_bukan_wav(self, tmp_path: Path) -> None:
        bad = tmp_path / "bogus.wav"
        bad.write_bytes(b"not a wav file")
        result = runner.invoke(app, ["verify", str(bad)])
        assert result.exit_code == 1
