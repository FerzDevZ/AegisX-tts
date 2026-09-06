"""Registry pesan i18n server (docs/04 §7) — id, en, ms, jv.

v1: dictionary statis dengan format {placeholder}; Fluent .ftl menyusul
saat UI penuh (docs/04 §7.1). Fallback selalu 'en', default 'id'.
"""

from __future__ import annotations

from typing import Final

_MESSAGES: Final[dict[str, dict[str, str]]] = {
    "error_input_required": {
        "id": "Field 'input' wajib diisi.",
        "en": "Field 'input' is required.",
        "ms": "Medan 'input' diperlukan.",
        "jv": "Kolom 'input' kedah diisi.",
    },
    "error_text_too_long": {
        "id": "Teks maksimal {limit} karakter.",
        "en": "Text exceeds the maximum of {limit} characters.",
        "ms": "Teks melebihi had {limit} aksara.",
        "jv": "Teks maksimal {limit} aksara.",
    },
    "error_invalid_voice": {
        "id": "Suara '{voice}' tidak dikenal.",
        "en": "Unknown voice '{voice}'.",
        "ms": "Suara '{voice}' tidak dikenali.",
        "jv": "Suwara '{voice}' ora dikenal.",
    },
    "error_invalid_format": {
        "id": "Format '{fmt}' tidak didukung (wav, pcm, mp3, opus).",
        "en": "Format '{fmt}' is not supported (wav, pcm, mp3, opus).",
        "ms": "Format '{fmt}' tidak disokong (wav, pcm, mp3, opus).",
        "jv": "Format '{fmt}' ora didhukung (wav, pcm, mp3, opus).",
    },
}

_FALLBACK: Final[str] = "en"


def get_message(key: str, locale: str, **params: object) -> str:
    """Ambil pesan terlokalisasi dengan placeholder terisi.

    Fallback: locale diminta → en. Placeholder gaya {nama} diganti kwargs.
    """
    table = _MESSAGES.get(key, {})
    template = table.get(locale) or table.get(_FALLBACK) or key
    for name, value in params.items():
        template = template.replace("{" + name + "}", str(value))
    return template


def available_keys() -> tuple[str, ...]:
    """Daftar kunci pesan (dipakai CI key-parity check docs/06 §5.5)."""
    return tuple(_MESSAGES)
