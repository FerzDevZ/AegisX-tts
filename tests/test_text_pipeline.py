"""Unit test pipeline teks: TN, G2P, tokenizer (docs/02 §3, docs/06 §5.1)."""

from __future__ import annotations

import pytest

from aegisx_tts.errors import TextError
from aegisx_tts.text import text_to_tokens
from aegisx_tts.text.g2p import graphemes_to_phonemes
from aegisx_tts.text.normalize import normalize_text


class TestNormalizeId:
    """Tabel normalisasi wajib docs/02 §3.2."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("2026", "dua ribu dua puluh enam"),
            ("1945", "seribu sembilan ratus empat puluh lima"),
            ("Rp15.000", "lima belas ribu rupiah"),
            ("3,14", "tiga koma satu empat"),
            ("5 km", "lima kilometer"),
            ("10%", "sepuluh persen"),
            ("3 kg", "tiga kilogram"),
            ("sdr. Budi", "saudara Budi"),
            ("dll.", "dan lain-lain"),
            ("cth.", "contoh"),
            ("dsb.", "dan sebagainya"),
        ],
    )
    def test_normalisasi_id(self, raw: str, expected: str) -> None:
        assert normalize_text(raw, lang="id") == expected

    def test_tanggal_id(self) -> None:
        assert (
            normalize_text("17-08-2026", lang="id")
            == "tujuh belas Agustus dua ribu dua puluh enam"
        )

    def test_angka_besar_dengan_titik_ribuan(self) -> None:
        assert normalize_text("1.000.000", lang="id") == "satu juta"


class TestNormalizeEn:
    """Normalisasi English dasar."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("I have 2 cats", "I have two cats"),
            ("Mr. Smith", "Mister Smith"),
            ("Dr. Who", "Doctor Who"),
            ("50%", "fifty percent"),
        ],
    )
    def test_normalisasi_en(self, raw: str, expected: str) -> None:
        assert normalize_text(raw, lang="en") == expected


class TestG2P:
    """G2P rule-based id + dict pengecualian."""

    def test_kata_transparan_id(self) -> None:
        # Ortografi id fonemik: masing-masing huruf dipetakan langsung.
        assert graphemes_to_phonemes("bola", lang="id") == ["b", "o", "l", "a"]

    def test_dict_pengecualian_menang(self) -> None:
        # "nga" digabung menjadi satu fonem digraf via aturan; kata dari
        # dict pengecualian harus mengikuti dict, bukan aturan default.
        hasil = graphemes_to_phonemes("saya", lang="id")
        assert hasil == ["s", "a", "j", "a"]

    def test_bahasa_tak_didukung(self) -> None:
        with pytest.raises(TextError):
            graphemes_to_phonemes("hello", lang="fr")  # type: ignore[arg-type]


class TestTextToTokens:
    """Kontrak publik text_to_tokens (docs/02 §3.1 L1-L5)."""

    def test_happy_path_id(self) -> None:
        tokens = text_to_tokens("Bola", lang="id")
        assert tokens[0] == "<bos>"
        assert tokens[-1] == "<eos>"
        assert all(t != "_unk_" for t in tokens)

    def test_teks_kosong(self) -> None:
        with pytest.raises(TextError):
            text_to_tokens("", lang="id")

    def test_teks_whitespace_saja(self) -> None:
        with pytest.raises(TextError):
            text_to_tokens("   \n\t  ", lang="id")

    def test_teks_melebihi_batas(self) -> None:
        with pytest.raises(TextError):
            text_to_tokens("a" * 50_001, lang="id")

    def test_kontrol_karakter_dibuang(self) -> None:
        # Karakter kontrol (kecuali \n) disanitasi di L1 — hasil tetap valid.
        tokens = text_to_tokens("hallo\u0007dunia", lang="id")
        assert "<bos>" in tokens and "<eos>" in tokens

    def test_bahasa_tak_didukung(self) -> None:
        with pytest.raises(TextError):
            text_to_tokens("bonjour", lang="de")  # type: ignore[arg-type]
