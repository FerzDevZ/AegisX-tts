"""G2P rule-based untuk id/ms/jv — docs/02 §3.4.

Ortografi id sangat fonemik: mapping huruf→fonem hampir 1:1 dengan aturan
digraf (ng, ny, kh, sy) dan aturan vokal terbuka/tertutup. Modul ini murni
deterministik dan mudah dikoreksi via dict pengecualian CSV.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from aegisx_tts.constants import SUPPORTED_LANGUAGES, LanguageCode
from aegisx_tts.errors import TextError

_DICT_DIR: Final[Path] = Path(__file__).parent / "dicts"

# Vokal id/jv pada suku kata tertutup non-penekanan: /a/ → [ə] (docs/02 §3.4).
_DIGRAPH: Final[dict[str, str]] = {
    "ng": "ŋ",
    "ny": "ɲ",
    "kh": "x",
    "sy": "ʃ",
}

_CONSONANT_MAP: Final[dict[str, str]] = {
    "c": "tʃ",
    "j": "dʒ",
    "y": "j",
    "q": "ʔ",
    "x": "ks",
}

_VOWELS: Final[frozenset[str]] = frozenset("aioue")

_CONSONANTS: Final[frozenset[str]] = frozenset("bcdfghjklmnpqrstvwxyz")


def _load_dict(lang: LanguageCode) -> dict[str, list[str]]:
    """Muat dict pengecualian CSV (format: kata,fonem1|fonem2|...)."""
    csv_path = _DICT_DIR / f"{lang}.csv"
    if not csv_path.exists():
        return {}
    entries: dict[str, list[str]] = {}
    for line in csv_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        word, _, phonemes_raw = stripped.partition(",")
        phonemes = [p for p in phonemes_raw.split("|") if p]
        entries[word.lower()] = phonemes
    return entries


def _word_to_phonemes(word: str) -> list[str]:
    """Terapkan aturan digraf + konsonan + vokal pada satu kata lowercase."""
    phonemes: list[str] = []
    i = 0
    n = len(word)
    while i < n:
        pair = word[i : i + 2]
        if pair in _DIGRAPH:
            phonemes.append(_DIGRAPH[pair])
            i += 2
            continue
        ch = word[i]
        if ch in _CONSONANT_MAP:
            phonemes.append(_CONSONANT_MAP[ch])
        elif ch in _VOWELS:
            # Aturan schwa: /a/ → [ə] pada suku kata tertutup
            # (diikuti konsonan dan bukan vokal berikutnya).
            next_ch = word[i + 1] if i + 1 < n else ""
            prev_is_vowel = i > 0 and word[i - 1] in _VOWELS
            if ch == "a" and next_ch in _CONSONANTS and not prev_is_vowel:
                phonemes.append("ə")
            else:
                phonemes.append(ch)
        elif ch in _CONSONANTS:
            phonemes.append(ch)
        # karakter lain (termasuk apostrof) diabaikan
        i += 1
    return phonemes


def graphemes_to_phonemes(word: str, lang: LanguageCode) -> list[str]:
    """Konversi satu kata menjadi deret fonem.

    Untuk id/ms/jv: rule-based. Dict pengecualian CSV (jika ada) menang.
    Untuk en: sengaja belum diimplement — lihat raise di bawah.

    Raises:
        TextError: bila bahasa tidak didukung, atau untuk 'en'
            (jalur espeak-ng baru tersedia di M2 — docs/07).
    """
    if lang not in SUPPORTED_LANGUAGES:
        raise TextError(f"Bahasa tidak didukung: {lang!r} (didukung: {SUPPORTED_LANGUAGES})")
    if lang == "en":
        raise TextError(
            "G2P 'en' butuh espeak-ng (terpasang di M2, docs/07 roadmap); "
            "v0.1 hanya id/ms/jv rule-based."
        )
    lowered = word.lower()
    overrides = _load_dict(lang)
    if lowered in overrides:
        return list(overrides[lowered])
    return _word_to_phonemes(lowered)
