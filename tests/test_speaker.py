"""Unit test SpeakerProfile & safetensors IO (docs/06 §5.1 test_voice_state)."""

from __future__ import annotations

from pathlib import Path

import pytest
import torch

from aegisx_tts.constants import SAMPLE_RATE_HZ
from aegisx_tts.core.speaker import (
    ConsentMeta,
    SpeakerProfile,
    SpeakerSource,
    load_speaker_file,
    save_speaker,
)


def _make_profile(source: SpeakerSource = SpeakerSource.EXPORTED) -> SpeakerProfile:
    kv = torch.randn(4, 2, 8, 16)
    return SpeakerProfile(
        kv_cache=kv,
        sample_rate=SAMPLE_RATE_HZ,
        source=source,
        watermark_enabled=source is SpeakerSource.CLONED,
        consent=None,
    )


class TestSpeakerProfile:
    def test_sample_rate_salah_ditolak(self) -> None:
        with pytest.raises(ValueError, match="sample_rate"):
            SpeakerProfile(
                kv_cache=torch.randn(1, 2, 4, 8),
                sample_rate=16_000,
                source=SpeakerSource.EXPORTED,
                watermark_enabled=False,
            )

    def test_cloned_tanpa_watermark_ditolak_fail_closed(self) -> None:
        with pytest.raises(ValueError, match="watermark"):
            SpeakerProfile(
                kv_cache=torch.randn(1, 2, 4, 8),
                sample_rate=SAMPLE_RATE_HZ,
                source=SpeakerSource.CLONED,
                watermark_enabled=False,
            )


class TestSafetensorsIO:
    def test_round_trip(self, tmp_path: Path) -> None:
        path = tmp_path / "spk.safetensors"
        asli = _make_profile()
        save_speaker(asli, path)
        hasil = load_speaker_file(path)
        assert hasil.source is asli.source
        assert hasil.sample_rate == SAMPLE_RATE_HZ
        assert torch.equal(hasil.kv_cache, asli.kv_cache)

    def test_consent_meta_ikut_tersimpan(self, tmp_path: Path) -> None:
        path = tmp_path / "spk.safetensors"
        meta = ConsentMeta(
            tier="self-declared", declared_by="tester", timestamp="2026-09-06T00:00:00Z"
        )
        save_speaker(_make_profile(), path, consent_meta=meta)
        hasil = load_speaker_file(path)
        assert hasil.consent is not None
        assert hasil.consent.tier == "self-declared"

    def test_ekstensi_salah_ditolak(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="safetensors"):
            save_speaker(_make_profile(), tmp_path / "spk.pickle")

    def test_file_tidak_ada(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="ditemukan"):
            load_speaker_file(tmp_path / "hilang.safetensors")
