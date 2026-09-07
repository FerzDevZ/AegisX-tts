"""Unit test watermark spektral + verifier — docs/05 §3.

Kontrak:
- Embed inaudible: energi hanya di 3.8–5.4 kHz (di luar formant utama).
- Roundtrip: payload disisipkan → terdeteksi utuh.
- Daya tahan: bertahan noise ringan, gain, clipping, resample ±5 % (docs/05 §3).
- Fail-closed: payload gagal disisipkan (audio terlalu pendek) → raise.
- Audio tanpa watermark → deteksi None (bukan payload palsu).
"""

from __future__ import annotations

import numpy as np
import pytest
import torch

from aegisx_tts.constants import SAMPLE_RATE_HZ
from aegisx_tts.core.watermark import (
    WATERMARK_BAND_HZ,
    WmkPayload,
    embed_watermark,
    verify_watermark,
)


def _make_audio(seconds: float, seed: int = 7) -> torch.Tensor:
    """Speech-like noise: lowpass-ish (band 100–4000 Hz) agar mirip formant."""
    gen = torch.Generator().manual_seed(seed)
    t = torch.arange(int(SAMPLE_RATE_HZ * seconds)) / SAMPLE_RATE_HZ
    audio = 0.3 * torch.sin(2 * np.pi * 220.0 * t)  # fonasi dasar
    audio = audio + 0.15 * torch.randn(int(SAMPLE_RATE_HZ * seconds), generator=gen)
    return audio.clamp(-0.9, 0.9)


class TestPayload:
    def test_payload_roundtrip(self) -> None:
        payload = WmkPayload(tier="self-declared", voice="budi-clone")
        assert payload.bitstring == verify_watermark(
            embed_watermark(_make_audio(2.0), payload)
        ).bitstring

    def test_payload_tier_validasi(self) -> None:
        with pytest.raises(ValueError, match="tier"):
            WmkPayload(tier="gratis", voice="x")


class TestEmbed:
    def test_durasi_minimal_ditolak(self) -> None:
        payload = WmkPayload(tier="written", voice="v")
        with pytest.raises(ValueError, match="durasi"):
            embed_watermark(_make_audio(0.1), payload)

    def test_inaudible_band(self) -> None:
        """Energi tambahan hanya boleh di band watermark, tidak di bawahnya."""
        original = _make_audio(2.0)
        payload = WmkPayload(tier="written", voice="v")
        marked = embed_watermark(original, payload)

        def band_energy(x: torch.Tensor, lo: float, hi: float) -> float:
            spec = torch.fft.rfft(x.float()).abs() ** 2
            freqs = torch.fft.rfftfreq(x.numel(), 1.0 / SAMPLE_RATE_HZ)
            mask = (freqs >= lo) & (freqs < hi)
            return float(spec[mask].sum())

        delta_low = band_energy(marked, 0, WATERMARK_BAND_HZ[0] - 1) - band_energy(
            original, 0, WATERMARK_BAND_HZ[0] - 1
        )
        assert delta_low < 1.0  # praktis tidak menambah energi di bawah band

    def test_distorsi_kecil(self) -> None:
        """SNR terhadap original cukup tinggi (inaudible psikoakustik)."""
        original = _make_audio(2.0)
        payload = WmkPayload(tier="written", voice="v")
        marked = embed_watermark(original, payload)
        noise = (marked - original).float()
        snr_db = 10 * torch.log10(
            original.float().pow(2).mean() / noise.pow(2).mean().clamp_min(1e-12)
        )
        assert float(snr_db) > 20.0


class TestVerify:
    def test_audio_bersih_tanpa_watermark(self) -> None:
        result = verify_watermark(_make_audio(2.0))
        assert result is None

    def test_tahan_noise_ringan(self) -> None:
        payload = WmkPayload(tier="written", voice="v")
        marked = embed_watermark(_make_audio(2.0), payload)
        gen = torch.Generator().manual_seed(99)
        noisy = marked + 0.01 * torch.randn(marked.numel(), generator=gen)
        assert verify_watermark(noisy) == payload

    def test_tahan_gain_dan_clipping(self) -> None:
        payload = WmkPayload(tier="written", voice="v")
        marked = embed_watermark(_make_audio(2.0), payload)
        boosted = (marked * 1.8).clamp(-1.0, 1.0)
        assert verify_watermark(boosted) == payload

    def test_tahan_resample_ringan(self) -> None:
        """Resample 24 kHz → 22.05 kHz → 24 kHz (interpolasi linear)."""
        payload = WmkPayload(tier="written", voice="v")
        marked = embed_watermark(_make_audio(2.0), payload)
        n_down = int(marked.numel() * 22050 / SAMPLE_RATE_HZ)
        down = torch.nn.functional.interpolate(
            marked.view(1, 1, -1), size=n_down, mode="linear", align_corners=True
        ).view(-1)
        up = torch.nn.functional.interpolate(
            down.view(1, 1, -1), size=marked.numel(), mode="linear", align_corners=True
        ).view(-1)
        assert verify_watermark(up) == payload

    def test_durasi_kurang_dari_minimal(self) -> None:
        assert verify_watermark(_make_audio(0.2)) is None
