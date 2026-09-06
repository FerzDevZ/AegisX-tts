"""Unit test VoiceEncoder (docs/02 §2.3, AC-7 docs/01 §9b).

Properti yang dijamin:
1. Sampel < 5 s ditolak dengan pesan yang menyebut durasi terdeteksi (AC-7).
2. Sampel > 30 s ditolak (docs/04 §2.4).
3. Sample rate != 24 kHz ditolak.
4. Audio senyap (RMS ≈ 0) ditolak — tidak ada embedding dari silence.
5. Output: SpeakerProfile source=CLONED, watermark_enabled=True (fail-closed),
   kv_cache shape [n_layers, 2, prefix_len, d_total].
6. Determinisme: waveform sama → embedding bit-identik.
"""

from __future__ import annotations

import pytest
import torch

from aegisx_tts.constants import SAMPLE_RATE_HZ
from aegisx_tts.core.speaker import SpeakerSource
from aegisx_tts.core.voice_encoder import VoiceEncoder

LAYERS, PREFIX, HEADS, D_HEAD = 4, 32, 8, 16


def _waveform(seconds: float, seed: int = 7) -> torch.Tensor:
    g = torch.Generator().manual_seed(seed)
    n = int(seconds * SAMPLE_RATE_HZ)
    return 0.2 * torch.randn(1, n, generator=g)


def _make_encoder() -> VoiceEncoder:
    torch.manual_seed(20260906)
    return VoiceEncoder(n_layers=LAYERS, prefix_len=PREFIX, heads=HEADS, d_head=D_HEAD)


class TestValidasi:
    def test_durasi_minimum_disebut_di_pesan(self) -> None:
        enc = _make_encoder()
        with pytest.raises(ValueError, match=r"minimal 5.*2\.0"):
            enc.encode(_waveform(2.0), SAMPLE_RATE_HZ)

    def test_durasi_maksimum_ditolak(self) -> None:
        enc = _make_encoder()
        with pytest.raises(ValueError, match="30"):
            enc.encode(_waveform(35.0), SAMPLE_RATE_HZ)

    def test_sample_rate_salah_ditolak(self) -> None:
        enc = _make_encoder()
        with pytest.raises(ValueError, match="sample_rate|24000"):
            enc.encode(_waveform(10.0), 16_000)

    def test_audio_senyap_ditolak(self) -> None:
        enc = _make_encoder()
        silent = torch.zeros(1, SAMPLE_RATE_HZ * 10)
        with pytest.raises(ValueError, match="senyap|silence"):
            enc.encode(silent, SAMPLE_RATE_HZ)

    def test_dimensi_waveform_salah(self) -> None:
        enc = _make_encoder()
        with pytest.raises(ValueError, match="dimensi|shape"):
            enc.encode(torch.randn(SAMPLE_RATE_HZ * 10), SAMPLE_RATE_HZ)


class TestOutput:
    def test_happy_path_10_detik(self) -> None:
        enc = _make_encoder()
        profile = enc.encode(_waveform(10.0), SAMPLE_RATE_HZ)
        assert profile.source is SpeakerSource.CLONED
        assert profile.watermark_enabled is True
        assert profile.sample_rate == SAMPLE_RATE_HZ
        assert tuple(profile.kv_cache.shape) == (LAYERS, 2, PREFIX, HEADS * D_HEAD)

    def test_determinisme(self) -> None:
        enc = _make_encoder()
        enc.eval()
        wave = _waveform(6.0)
        with torch.no_grad():
            a = enc.encode(wave, SAMPLE_RATE_HZ)
            b = enc.encode(wave, SAMPLE_RATE_HZ)
        assert torch.equal(a.kv_cache, b.kv_cache)
