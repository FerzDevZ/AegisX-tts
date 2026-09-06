"""Tokenizer fonem → token model (docs/02 §3.1 L1–L5)."""

from __future__ import annotations

import re
import unicodedata
from typing import Final

from aegisx_tts.constants import MAX_TEXT_CHARS, SUPPORTED_LANGUAGES, LanguageCode
from aegisx_tts.errors import TextError
from aegisx_tts.text.g2p import graphemes_to_phonemes

_BOS: Final[str] = "<bos>"
_EOS: Final[str] = "<eos>"
_UNK: Final[str] = "_unk_"


def sanitize(text: str) -> str:
    """L1: NFC + buang karakter kontrol kecuali newline (docs/02 §8)."""
    cleaned = unicodedata.normalize("NFC", text)
    return "".join(
        ch for ch in cleaned if ch == "\n" or not unicodedata.category(ch).startswith("C")
    )


def _split_words(text: str) -> list[str]:
    """Pemisah kata sederhana: huruf/angka menyatu, sisanya pemisah."""
    return [w for w in re.split(r"[^\w]+", text, flags=re.UNICODE) if w]


def text_to_tokens(text: str, lang: LanguageCode) -> list[str]:
    """Pipeline penuh L1→L5: sanitize → TN → G2P per kata → token + BOS/EOS.

    Raises:
        TextError: teks kosong/whitespace, melebihi batas, atau bahasa
            tidak didukung.
    """
    if lang not in SUPPORTED_LANGUAGES:
        raise TextError(f"Bahasa tidak didukung: {lang!r} (didukung: {SUPPORTED_LANGUAGES})")
    if len(text) > MAX_TEXT_CHARS:
        raise TextError(f"Teks melebihi batas {MAX_TEXT_CHARS} karakter")
    cleaned = sanitize(text)
    if not cleaned.strip():
        raise TextError("Teks kosong atau hanya whitespace")

    tokens: list[str] = [_BOS]
    unknown_seen = False
    for word in _split_words(cleaned):
        if word.isalpha():
            phonemes = graphemes_to_phonemes(word, lang)
        elif word.isdigit():
            # TN id/en sudah mengubah angka ke kata; digit sisa (mis. dalam
            # kode "7"), dibaca per digit via fonem nama digit id.
            phonemes = _digits_to_phonemes_id(word)
        else:
            phonemes = [_UNK]
            unknown_seen = True
        tokens.extend(phonemes)
    tokens.append(_EOS)
    if unknown_seen:
        # Eksplisit, tidak silent (docs/02 §8): pemanggil dapat memutuskan.
        raise TextError("Terdapat karakter yang tidak dapat dipetakan ke fonem (_unk_)")
    return tokens


def _digits_to_phonemes_id(digits: str) -> list[str]:
    """Fonem nama digit Indonesia: 0–9 → nol..sembilan."""
    digit_words: Final[dict[str, str]] = {
        "0": "nol", "1": "satu", "2": "dua", "3": "tiga", "4": "empat",
        "5": "lima", "6": "enam", "7": "tujuh", "8": "delapan", "9": "sembilan",
    }
    phonemes: list[str] = []
    for d in digits:
        phonemes.extend(graphemes_to_phonemes(digit_words[d], "id"))
    return phonemes
