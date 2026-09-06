"""Synth: mesin sintesis AegisX-TTS (kontrak publik docs/02 §6.1).

Status v0.1 (M1): kontrak API terkunci dan validasi input aktif; bobot
neural baru tersedia di M2 (docs/07 roadmap). Metode yang membutuhkan
bobot melempar ModelWeightsUnavailable dengan pesan eksplisit — bukan
stub diam-diam.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Literal

import torch

from aegisx_tts.constants import (
    MAX_TEXT_CHARS,
    SUPPORTED_LANGUAGES,
    LanguageCode,
)
from aegisx_tts.core.speaker import SpeakerProfile
from aegisx_tts.errors import ModelWeightsUnavailable, TextError

Variant = Literal["base", "24l"]


class Synth:
    """Mesin sintesis CPU-first. Satu instance per thread (docs/04 §3.2)."""

    @classmethod
    def load(
        cls,
        language: LanguageCode,
        variant: Variant = "base",
        config: str | Path | None = None,
        quantize: bool = False,
    ) -> Synth:
        """Muat mesin untuk bahasa tertentu.

        Raises:
            TextError: bila bahasa tidak didukung.
            ModelWeightsUnavailable: bobot varian belum dirilis (M2).
        """
        if language not in SUPPORTED_LANGUAGES:
            raise TextError(
                f"Bahasa tidak didukung: {language!r} (didukung: {SUPPORTED_LANGUAGES})"
            )
        if variant not in ("base", "24l"):
            raise TextError(f"Varian tidak dikenal: {variant!r} (pilih: base | 24l)")
        if config is not None and not Path(config).exists():
            raise ModelWeightsUnavailable(f"File config tidak ditemukan: {config}")
        raise ModelWeightsUnavailable(
            f"Bobot model '{language}' varian '{variant}' belum dirilis "
            "(target: M2 docs/07 roadmap). Pipeline teks & speaker IO sudah aktif."
        )

    def __init__(self) -> None:  # pragma: no cover - dipakai via load() di M2
        raise ModelWeightsUnavailable(
            "Instansiasi langsung dinonaktifkan pada v0.1; gunakan Synth.load()."
        )

    def speaker_from_preset(self, name: str) -> SpeakerProfile:
        raise ModelWeightsUnavailable("Katalog preset hadir bersama bobot di M2.")

    def speaker_from_audio(self, path: str | Path) -> SpeakerProfile:
        raise ModelWeightsUnavailable("Voice cloning hadir bersama bobot di M2.")

    def speaker_from_file(self, path: str | Path) -> SpeakerProfile:
        from aegisx_tts.core.speaker import load_speaker_file

        return load_speaker_file(path)

    def synthesize(self, speaker: SpeakerProfile, text: str) -> torch.Tensor:
        self._validate_request(speaker, text)
        raise ModelWeightsUnavailable("Sintesis neural aktif di M2.")

    def stream(
        self, speaker: SpeakerProfile, text: str, chunk_ms: int = 80
    ) -> Iterator[torch.Tensor]:
        self._validate_request(speaker, text)
        if chunk_ms <= 0 or chunk_ms % 80 != 0:
            raise TextError("chunk_ms harus kelipatan 80 dan positif")
        raise ModelWeightsUnavailable("Streaming neural aktif di M2.")

    @staticmethod
    def _validate_request(speaker: SpeakerProfile, text: str) -> None:
        if not isinstance(speaker, SpeakerProfile):
            raise TextError("Argumen 'speaker' harus SpeakerProfile")
        if not text or not text.strip():
            raise TextError("Teks kosong")
        if len(text) > MAX_TEXT_CHARS:
            raise TextError(f"Teks melebihi batas {MAX_TEXT_CHARS} karakter")


__all__ = ["Synth"]
