"""Hierarki error AegisX-TTS — semua error publik diketik dan berpesan jelas."""

from __future__ import annotations


class AegisXTTSError(Exception):
    """Base error semua error AegisX-TTS."""


class TextError(AegisXTTSError):
    """Input teks tidak valid (kosong, melebihi batas, bahasa tak didukung)."""


class ConfigError(AegisXTTSError):
    """Konfigurasi model tidak valid atau tidak ditemukan."""


class SpeakerError(AegisXTTSError):
    """Profile speaker tidak valid (file korup, metadata hilang)."""


class ModelWeightsUnavailable(AegisXTTSError):
    """Bobot model belum tersedia untuk varian yang diminta (lihat docs/07 roadmap)."""
