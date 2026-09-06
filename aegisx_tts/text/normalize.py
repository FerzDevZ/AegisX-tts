"""Text normalization (TN) per bahasa — lapisan L3 docs/02 §3.1.

Pipeline: angka → kata, tanggal, mata uang, persen, satuan, singkatan.
Semua substitusi bersifat idempoten dan diuji di tests/test_text_pipeline.py.
"""

from __future__ import annotations

import re
from typing import Final

from aegisx_tts.constants import SUPPORTED_LANGUAGES, LanguageCode
from aegisx_tts.errors import TextError
from aegisx_tts.text.numbers_en import digits_to_words_en, int_to_words_en
from aegisx_tts.text.numbers_id import digits_to_words_id, int_to_words_id, month_name_id

_WS_RE: Final[re.Pattern[str]] = re.compile(r"\s+")

_ABBREV_ID: Final[dict[str, str]] = {
    "sdr.": "saudara",
    "sdri.": "saudari",
    "dll.": "dan lain-lain",
    "cth.": "contoh",
    "dsb.": "dan sebagainya",
}

_ABBREV_EN: Final[dict[str, str]] = {
    "Mr.": "Mister",
    "Mrs.": "Missus",
    "Ms.": "Miss",
    "Dr.": "Doctor",
}

_UNIT_SUFFIX_ID: Final[dict[str, str]] = {
    "km": "kilometer",
    "kg": "kilogram",
    "m": "meter",
    "cm": "sentimeter",
    "s": "detik",
    "jam": "jam",
}

_MONTH_NAME_TO_NUM: Final[dict[str, int]] = {
    name.lower(): i + 1 for i, name in enumerate(
        (
            "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember",
        )
    )
}


def _number_to_words(lang: LanguageCode, n: int) -> str:
    if lang == "id":
        return int_to_words_id(n)
    return int_to_words_en(n)


def _decimal_to_words(lang: LanguageCode, int_part: str, frac_part: str) -> str:
    sep = "koma" if lang == "id" else "point"
    digits = digits_to_words_id(frac_part) if lang == "id" else digits_to_words_en(frac_part)
    return f"{_number_to_words(lang, int(int_part))} {sep} {digits}"


def _replace_number_tokens(lang: LanguageCode, text: str) -> str:
    """Ganti token numerik sisa menjadi kata (locale-aware).

    id: titik = pemisah ribuan, koma = desimal. en: sebaliknya.
    """
    if lang == "id":
        decimal_re = re.compile(r"\b(\d{1,9}),(\d+)\b")
        thousand_re = re.compile(r"\b\d{1,3}(?:\.\d{3})+\b")
    else:
        decimal_re = re.compile(r"\b(\d{1,9})\.(\d+)\b")
        thousand_re = re.compile(r"\b\d{1,3}(?:,\d{3})+\b")
    plain_re = re.compile(r"\b\d{1,9}\b")

    def sub_decimal(m: re.Match[str]) -> str:
        return _decimal_to_words(lang, m.group(1), m.group(2))

    def sub_thousand(m: re.Match[str]) -> str:
        return _number_to_words(lang, int(m.group(0).replace(".", "").replace(",", "")))

    def sub_plain(m: re.Match[str]) -> str:
        return _number_to_words(lang, int(m.group(0)))

    text = decimal_re.sub(sub_decimal, text)
    text = thousand_re.sub(sub_thousand, text)
    text = plain_re.sub(sub_plain, text)
    return text


def _normalize_id(text: str) -> str:
    # Urutan wajib: pola ber-konteks (Rp/%/satuan/tanggal) SEBELUM angka
    # generik, agar digit tidak sudah terkonversi jadi kata.

    # Mata uang: Rp15.000 → lima belas ribu rupiah
    text = re.sub(
        r"\bRp\s?([\d.]+)\b",
        lambda m: f"{_replace_number_tokens('id', m.group(1))} rupiah",
        text,
    )

    # Persen: 10% → sepuluh persen
    text = re.sub(r"\b(\d{1,3})%", lambda m: f"{int_to_words_id(int(m.group(1)))} persen", text)

    # Satuan: 5 km → lima kilometer
    units = "|".join(_UNIT_SUFFIX_ID)
    text = re.sub(
        rf"\b(\d+)\s?({units})\b",
        lambda m: f"{int_to_words_id(int(m.group(1)))} {_UNIT_SUFFIX_ID[m.group(2)]}",
        text,
    )

    # Tanggal: 17-08-2026 → tujuh belas Agustus dua ribu dua puluh enam
    def sub_date(m: re.Match[str]) -> str:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return (
            f"{int_to_words_id(day)} {month_name_id(month)} "
            f"{int_to_words_id(year)}"
        )

    text = re.sub(r"\b(\d{1,2})-(\d{1,2})-(\d{4})\b", sub_date, text)

    # Angka generik paling akhir
    text = _replace_number_tokens("id", text)

    # Singkatan
    for abbrev, full in _ABBREV_ID.items():
        text = text.replace(abbrev, full)
    return text


def _normalize_en(text: str) -> str:
    # Persen sebelum angka generik.
    text = re.sub(r"\b(\d{1,3})%", lambda m: f"{int_to_words_en(int(m.group(1)))} percent", text)
    text = _replace_number_tokens("en", text)

    for abbrev, full in _ABBREV_EN.items():
        text = re.sub(rf"\b{re.escape(abbrev)}", full, text)
    return text


def _normalize_ms(text: str) -> str:
    """ms memakai mesin id + leksikon ringgit (docs/02 §3.3)."""
    text = re.sub(
        r"\bRM\s?([\d.]+)\b",
        lambda m: f"{_replace_number_tokens('id', m.group(1))} ringgit",
        text,
    )
    return _normalize_id(text)


def _normalize_jv(text: str) -> str:
    """v1: jv mewarisi mesin id (ngoko lughawi) — lihat docs/02 §3.3."""
    return _normalize_id(text)


def normalize_text(text: str, lang: LanguageCode) -> str:
    """Normalisasi teks ke bentuk lisan untuk bahasa yang didukung.

    Raises:
        TextError: bila bahasa tidak didukung.
    """
    if lang not in SUPPORTED_LANGUAGES:
        raise TextError(f"Bahasa tidak didukung: {lang!r} (didukung: {SUPPORTED_LANGUAGES})")
    dispatch = {
        "id": _normalize_id,
        "en": _normalize_en,
        "ms": _normalize_ms,
        "jv": _normalize_jv,
    }
    normalized = dispatch[lang](text)
    return _WS_RE.sub(" ", normalized).strip()
