"""ModelConfig: skema konfigurasi model (docs/02 §7) + resolver sumber config.

Keamanan (mitigasi T3/T8, RFC.md §6):
- Strict pydantic: field tak dikenal ditolak.
- URL config wajib pin `@revision` dan domain masuk whitelist.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from aegisx_tts.constants import MAX_TEXT_CHARS, SAMPLE_RATE_HZ, SUPPORTED_LANGUAGES, LanguageCode
from aegisx_tts.errors import ConfigError

_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset(
    {"huggingface.co", "raw.githubusercontent.com"}
)

_REVISION_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{7,40}$")


class BackboneConfig(BaseModel):
    """Spesifikasi backbone Transformer (docs/02 §2.2)."""

    model_config = ConfigDict(extra="forbid")

    layers: int = Field(ge=4, le=48)
    d_model: int = Field(ge=256, le=2048)
    heads: int = Field(ge=1, le=32)
    d_ff: int = Field(ge=512, le=8192)


class CodecConfig(BaseModel):
    """Spesifikasi codec RVQ (docs/02 §4) — invarian 24 kHz / 80 ms."""

    model_config = ConfigDict(extra="forbid")

    sample_rate: int
    frame_ms: int
    rvq_levels: int = Field(ge=1, le=32)
    codebook_size: int = Field(ge=256, le=4096)

    @field_validator("sample_rate")
    @classmethod
    def _sample_rate_locked(cls, v: int) -> int:
        if v != SAMPLE_RATE_HZ:
            raise ValueError(f"sample_rate terkunci pada {SAMPLE_RATE_HZ} (docs/02 §4)")
        return v

    @field_validator("frame_ms")
    @classmethod
    def _frame_ms_locked(cls, v: int) -> int:
        if v != 80:
            raise ValueError("frame_ms terkunci pada 80 (docs/02 §4)")
        return v


class ModelSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backbone: BackboneConfig
    codec: CodecConfig


class VoiceEntry(BaseModel):
    """Entri katalog suara (docs/01 REQ-050)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    file: str = Field(min_length=1)
    license: str = Field(min_length=1)


class WatermarkConfig(BaseModel):
    """docs/05 §3 — default fail-closed (enabled)."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    strength: float = Field(default=0.4, ge=0.0, le=1.0)


class LimitsConfig(BaseModel):
    """Batas server/CLI (mitigasi T4, docs/04 §4.4)."""

    model_config = ConfigDict(extra="forbid")

    max_text_chars: int = Field(default=MAX_TEXT_CHARS, ge=1)


class ModelConfig(BaseModel):
    """Akar konfigurasi model AegisX-TTS."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(ge=1, le=1)
    model: ModelSpec
    language: LanguageCode
    text: dict[str, str] = Field(default_factory=dict)
    voices: list[VoiceEntry] = Field(default_factory=list)
    watermark: WatermarkConfig = Field(default_factory=WatermarkConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)

    @field_validator("language")
    @classmethod
    def _language_supported(cls, v: str) -> str:
        if v not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Bahasa tidak didukung: {v!r} (didukung: {SUPPORTED_LANGUAGES})")
        return v

    @classmethod
    def from_yaml(cls, path: str | Path) -> ModelConfig:
        """Muat config dari file YAML.

        Raises:
            ConfigError: file tidak ada, YAML invalid, atau skema melanggar.
        """
        p = Path(path)
        if not p.exists():
            raise ConfigError(f"File config tidak ditemukan: {p}")
        try:
            raw = yaml.safe_load(p.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ConfigError(f"YAML tidak valid: {exc}") from exc
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> ModelConfig:
        if not isinstance(raw, dict):
            raise ConfigError("Config harus berupa mapping YAML/JSON")
        try:
            return cls.model_validate(raw)
        except ValidationError as exc:
            raise ConfigError(f"Config melanggar skema: {exc}") from exc


def parse_config_dict(raw: dict[str, Any] | None) -> ModelConfig:
    """API publik: validasi dict config → ModelConfig.

    Raises:
        ConfigError: skema melanggar (field tak dikenal, invarian, bahasa).
    """
    return ModelConfig.from_dict(raw)


class ConfigSource:
    """Hasil resolve sumber config (lokal vs remote)."""

    def __init__(self, raw: str, *, is_local: bool, url: str | None, revision: str | None) -> None:
        self.raw = raw
        self.is_local = is_local
        self.url = url
        self.revision = revision


def resolve_config_source(source: str) -> ConfigSource:
    """Resolve path lokal / URL https / hf:// dengan aturan keamanan T3.

    Raises:
        ConfigError: URL tanpa `@revision`, domain di luar whitelist,
            atau skema tak dikenal.
    """
    if source.startswith("hf://"):
        rest = source[len("hf://") :]
        if "@" not in rest:
            raise ConfigError("hf:// URL wajib pin revision: hf://<repo>/<path>@<hash>")
        repo_path, _, revision = rest.rpartition("@")
        if not repo_path or not _REVISION_RE.match(revision):
            raise ConfigError(f"Revision tidak valid: {revision!r}")
        return ConfigSource(source, is_local=False, url=source, revision=revision)

    if source.startswith("https://"):
        if "@" not in source:
            raise ConfigError(
                "URL https wajib pin revision: https://.../<file>.yaml@<commit-hash>"
            )
        url_base, _, revision = source.rpartition("@")
        if not _REVISION_RE.match(revision):
            raise ConfigError(f"Revision tidak valid: {revision!r}")
        host = urlparse(url_base).hostname or ""
        if host not in _ALLOWED_HOSTS:
            raise ConfigError(
                f"Domain tidak di whitelist: {host!r} (diizinkan: {sorted(_ALLOWED_HOSTS)})"
            )
        return ConfigSource(source, is_local=False, url=url_base, revision=revision)

    if "://" in source:
        raise ConfigError(f"Skema tidak didukung: {source.split('://')[0]!r}")

    return ConfigSource(source, is_local=True, url=None, revision=None)
