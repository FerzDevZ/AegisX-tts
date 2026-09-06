"""Konversi angka ke kata (English) — docs/02 §3.3."""

from __future__ import annotations

_SMALL = (
    "zero", "one", "two", "three", "four", "five", "six", "seven",
    "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
    "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
)
_TENS = (
    "", "", "twenty", "thirty", "forty", "fifty",
    "sixty", "seventy", "eighty", "ninety",
)
_SCALE = (
    (1_000_000_000, "billion"),
    (1_000_000, "million"),
    (1_000, "thousand"),
    (100, "hundred"),
)


def int_to_words_en(n: int) -> str:
    """Ubah bilangan bulat non-negatif menjadi kata English.

    Raises:
        ValueError: bila n negatif atau melebihi 999 miliar.
    """
    if n < 0:
        raise ValueError(f"Negative numbers not supported: {n}")
    if n >= 1_000_000_000_000:
        raise ValueError(f"Number too large (>= 1 trillion): {n}")
    if n < 20:
        return _SMALL[n]
    if n < 100:
        tens = _TENS[n // 10]
        return f"{tens}-{_SMALL[n % 10]}" if n % 10 else tens
    for threshold, name in _SCALE:
        if n >= threshold:
            head = int_to_words_en(n // threshold)
            tail = int_to_words_en(n % threshold) if n % threshold else ""
            return f"{head} {name} {tail}".strip()
    raise AssertionError("unreachable")  # pragma: no cover


def digits_to_words_en(digits: str) -> str:
    """Ubah deret digit menjadi kata per digit (untuk desimal)."""
    return " ".join(_SMALL[int(d)] for d in digits)
