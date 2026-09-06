"""Konversi angka ke kata (Bahasa Indonesia) — docs/02 §3.2."""

from __future__ import annotations

_SATUAN = (
    "nol", "satu", "dua", "tiga", "empat", "lima",
    "enam", "tujuh", "delapan", "sembilan", "sepuluh", "sebelas",
)

_BULAN_ID = (
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
)


def int_to_words_id(n: int) -> str:
    """Ubah bilangan bulat non-negatif menjadi kata Bahasa Indonesia.

    Raises:
        ValueError: bila n negatif atau melebihi 999 juta.
    """
    if n < 0:
        raise ValueError(f"Bilangan negatif tidak didukung: {n}")
    if n >= 1_000_000_000:
        raise ValueError(f"Bilangan terlalu besar (>= 1 miliar): {n}")
    if n < 12:
        return _SATUAN[n]
    if n < 20:
        return f"{_SATUAN[n - 10]} belas"
    if n < 100:
        puluh = f"{_SATUAN[n // 10]} puluh"
        return f"{puluh} {_SATUAN[n % 10]}" if n % 10 else puluh
    if n < 200:
        ratus = "seratus"
        return f"{ratus} {int_to_words_id(n % 100)}" if n % 100 else ratus
    if n < 1_000:
        ratus = f"{_SATUAN[n // 100]} ratus"
        return f"{ratus} {int_to_words_id(n % 100)}" if n % 100 else ratus
    if n < 2_000:
        ribu = "seribu"
        return f"{ribu} {int_to_words_id(n % 1000)}" if n % 1000 else ribu
    if n < 1_000_000:
        ribu = f"{int_to_words_id(n // 1000)} ribu"
        return f"{ribu} {int_to_words_id(n % 1000)}" if n % 1000 else ribu
    juta = f"{int_to_words_id(n // 1_000_000)} juta"
    return f"{juta} {int_to_words_id(n % 1_000_000)}" if n % 1_000_000 else juta


def digits_to_words_id(digits: str) -> str:
    """Ubah deret digit (mis. desimal '14') menjadi kata per digit."""
    return " ".join(_SATUAN[int(d)] for d in digits)


def month_name_id(month: int) -> str:
    """Nama bulan Indonesia (1–12).

    Raises:
        ValueError: bila bulan di luar 1–12.
    """
    if not 1 <= month <= 12:
        raise ValueError(f"Bulan tidak valid: {month}")
    return _BULAN_ID[month - 1]
