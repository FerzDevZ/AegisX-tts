"""Konstanta inti AegisX-TTS."""

from __future__ import annotations

from typing import Literal

LanguageCode = Literal["id", "en", "ms", "jv"]

SUPPORTED_LANGUAGES: tuple[LanguageCode, ...] = ("id", "en", "ms", "jv")

DEFAULT_LANGUAGE: LanguageCode = "id"

SAMPLE_RATE_HZ = 24_000
FRAME_MS = 80
SAMPLES_PER_FRAME = SAMPLE_RATE_HZ * FRAME_MS // 1000  # 1920
MAX_TEXT_CHARS = 50_000
MIN_REF_AUDIO_SECONDS = 5.0
MAX_REF_AUDIO_SECONDS = 30.0
