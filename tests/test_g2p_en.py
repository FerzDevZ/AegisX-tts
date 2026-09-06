"""Unit test G2P English via espeak-ng (docs/02 §3.4).

Test integrasi opsional: jika biner espeak-ng tidak tersedia (lingkungan
lokal tanpa root), test di-skip dengan alasan eksplisit — CI memasang
espeak-ng sehingga jalur ini selalu terverifikasi di runner.
"""

from __future__ import annotations

import shutil

import pytest

from aegisx_tts.errors import TextError
from aegisx_tts.text.g2p_en import graphemes_to_phonemes_en

_ESPEAK_AVAILABLE = shutil.which("espeak-ng") is not None

_skip_no_espeak = pytest.mark.skipif(
    not _ESPEAK_AVAILABLE, reason="espeak-ng tidak terpasang di sistem ini (CI memasangnya)"
)


@_skip_no_espeak
class TestG2PEn:
    def test_kata_umum(self) -> None:
        fonem = graphemes_to_phonemes_en("hello")
        assert fonem and all(isinstance(p, str) for p in fonem)
        # 'hello' → h ə l oʊ (espeak en-us); cukup cek fonem awal & panjang.
        assert fonem[0] == "h"
        assert len(fonem) >= 3

    def test_kapitalisasi_tidak_mengubah_hasil(self) -> None:
        assert graphemes_to_phonemes_en("Hello") == graphemes_to_phonemes_en("hello")

    def test_teks_multi_kata(self) -> None:
        fonem = graphemes_to_phonemes_en("good morning")
        assert len(fonem) > len(graphemes_to_phonemes_en("good"))

    def test_karakter_non_latin_ditolak_bersih(self) -> None:
        with pytest.raises(TextError):
            graphemes_to_phonemes_en("café　日本")


class TestFallbackTanpaEspeak:
    def test_pesan_error_jelas_ketika_biner_hilang(self, monkeypatch: pytest.MonkeyPatch) -> None:
        if _ESPEAK_AVAILABLE:
            monkeypatch.setattr(
                "aegisx_tts.text.g2p_en._find_espeak_binary", lambda: None
            )
        with pytest.raises(TextError, match="espeak-ng"):
            graphemes_to_phonemes_en("hello")
