"""G2P English via espeak-ng — docs/02 §3.4 (ADR-004).

en memakai espeak-ng (ortografi Inggris tidak transparan untuk rule-based).
Modul ini mengeksekusi biner `espeak-ng --ipa` dan mengubah output IPA
menjadi daftar fonem. Bila biner tidak ada → TextError dengan pesan
install yang jelas (tidak ada fallback diam-diam).
"""

from __future__ import annotations

import shutil
import subprocess
import unicodedata
from typing import Final

from aegisx_tts.errors import TextError

_TIMEOUT_SECONDS: Final[float] = 10.0
_MAX_INPUT_CHARS: Final[int] = 4_000

_IPA_DISCARD: Final[frozenset[str]] = frozenset(
    {"ˈ", "ˌ", "ː", "̃", " ", "\u200b", "\u2060", "(", ")", "{", "}", "'", '"'}
)


def _find_espeak_binary() -> str | None:
    return shutil.which("espeak-ng") or shutil.which("espeak")


def _espeak_ipa(text: str, binary: str) -> str:
    """Jalankan espeak-ng dan kembalikan output IPA satu baris.

    Raises:
        TextError: input kosong, binary gagal, timeout, atau output kosong.
    """
    if not text or not text.strip():
        raise TextError("Teks kosong untuk G2P en")
    if len(text) > _MAX_INPUT_CHARS:
        raise TextError(f"Teks G2P en melebihi {_MAX_INPUT_CHARS} karakter")
    try:
        proc = subprocess.run(
            [binary, "-q", "--ipa", "-v", "en-us", "--sep= ", "-x", text],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=True,
        )
    except subprocess.TimeoutExpired as exc:
        raise TextError("espeak-ng timeout — teks terlalu panjang atau sistem sibuk") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip().splitlines()
        raise TextError(f"espeak-ng gagal: {detail[0] if detail else exc.returncode}") from exc
    return proc.stdout.strip()


def _ipa_to_phonemes(ipa: str) -> list[str]:
    """Ubah string IPA espeak menjadi daftar fonem sederhana."""
    normalized = unicodedata.normalize("NFC", ipa)
    phonemes: list[str] = []
    for token in normalized.split():
        if token in _IPA_DISCARD:
            continue
        cleaned = "".join(ch for ch in token if ch not in _IPA_DISCARD)
        if cleaned:
            phonemes.append(cleaned)
    return phonemes


def graphemes_to_phonemes_en(text: str) -> list[str]:
    """Konversi teks English menjadi deret fonem via espeak-ng.

    Raises:
        TextError: espeak-ng tidak terpasang, input invalid, atau
            eksekusi gagal.
    """
    binary = _find_espeak_binary()
    if binary is None:
        raise TextError(
            "G2P 'en' membutuhkan espeak-ng. Install: apt install espeak-ng "
            "(atau brew install espeak-ng); lihat docs/02 §3.4"
        )
    if any(ord(ch) > 0x2FFF for ch in text):
        raise TextError("Teks G2P en hanya mendukung aksara Latin")
    ipa = _espeak_ipa(text, binary)
    phonemes = _ipa_to_phonemes(ipa)
    if not phonemes:
        raise TextError("espeak-ng mengembalikan output kosong")
    return phonemes
