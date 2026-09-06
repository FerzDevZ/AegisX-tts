"""Kontrak tipe inti AegisX-TTS: SpeakerProfile & ConsentMeta.

SpeakerProfile = kondisioner suara (prefix KV-cache per layer) yang immutable
dan portable via safetensors. Lihat docs/02 §2.3 dan RFC.md §5.2.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import torch

from aegisx_tts.constants import SAMPLE_RATE_HZ


class SpeakerSource(Enum):
    """Asal-usul profile speaker."""

    PRESET = "preset"
    CLONED = "cloned"
    EXPORTED = "exported"


@dataclass(frozen=True)
class ConsentMeta:
    """Metadata persetujuan pemilik suara (docs/05 §2.1)."""

    tier: str  # self-declared | written | commercial
    declared_by: str
    timestamp: str


@dataclass(frozen=True)
class SpeakerProfile:
    """Kondisioner suara immutable: prefix KV-cache per layer.

    Attributes:
        kv_cache: tensor [n_layers, 2, seq_len, d_head] (K dan V terpisah).
        sample_rate: selalu 24_000.
        source: asal profile (PRESET / CLONED / EXPORTED).
        watermark_enabled: wajib True untuk source CLONED (fail-closed).
    """

    kv_cache: torch.Tensor
    sample_rate: int
    source: SpeakerSource
    watermark_enabled: bool
    consent: ConsentMeta | None = None

    def __post_init__(self) -> None:
        if self.sample_rate != SAMPLE_RATE_HZ:
            raise ValueError(
                f"sample_rate harus {SAMPLE_RATE_HZ}, dapat {self.sample_rate}"
            )
        if self.source is SpeakerSource.CLONED and not self.watermark_enabled:
            raise ValueError(
                "Profile CLONED wajib watermark_enabled=True (fail-closed, docs/05 §3)"
            )


def save_speaker(
    speaker: SpeakerProfile,
    path: str | Path,
    *,
    consent_meta: ConsentMeta | None = None,
) -> Path:
    """Simpan SpeakerProfile ke file safetensors beserta metadata.

    Metadata disimpan sebagai JSON string di header safetensors.
    Tensor disimpan tanpa komputasi ulang sehingga load ~50 ms (docs/02 §2.3).

    Raises:
        ValueError: bila kv_cache bukan tensor float atau path kosong.
    """
    try:
        from safetensors.torch import save_file
    except ImportError as exc:  # pragma: no cover - guard dependency opsional
        raise ImportError(
            "safetensors belum terpasang. Install: pip install safetensors"
        ) from exc
    out_path = Path(path)
    if out_path.suffix != ".safetensors":
        raise ValueError(f"File output harus .safetensors, dapat: {out_path.name}")

    meta: dict[str, Any] = {
        "format": "aegisx-speaker-v1",
        "sample_rate": speaker.sample_rate,
        "source": speaker.source.value,
        "watermark_enabled": speaker.watermark_enabled,
    }
    if consent_meta is not None:
        meta["consent"] = {
            "tier": consent_meta.tier,
            "declared_by": consent_meta.declared_by,
            "timestamp": consent_meta.timestamp,
        }

    save_file(
        {"kv_cache": speaker.kv_cache.contiguous()},
        str(out_path),
        metadata={
            k: json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else str(v)
            for k, v in meta.items()
        },
    )
    return out_path


def load_speaker_file(path: str | Path) -> SpeakerProfile:
    """Muat SpeakerProfile dari safetensors (jalur cepat, tanpa encoder).

    Raises:
        ValueError: bila format/metadata tidak valid.
    """
    try:
        from safetensors import safe_open
    except ImportError as exc:  # pragma: no cover - guard dependency opsional
        raise ImportError(
            "safetensors belum terpasang. Install: pip install safetensors"
        ) from exc

    in_path = Path(path)
    if not in_path.exists():
        raise ValueError(f"File speaker tidak ditemukan: {in_path}")

    from safetensors import safe_open

    with safe_open(str(in_path), framework="pt") as handle:
        header: dict[str, str] = dict(handle.metadata() or {})
        tensors = {key: handle.get_tensor(key) for key in handle.keys()}
    if "kv_cache" not in tensors:
        raise ValueError("File safetensors tidak berisi tensor 'kv_cache'")

    fmt = header.get("format")
    if fmt != "aegisx-speaker-v1":
        raise ValueError(f"Format speaker tak dikenal: {fmt!r}")

    source_raw = header.get("source", SpeakerSource.EXPORTED.value)
    try:
        source = SpeakerSource(source_raw)
    except ValueError as exc:
        raise ValueError(f"Source speaker tak dikenal: {source_raw!r}") from exc

    watermark = header.get("watermark_enabled", "True") == "True"
    consent: ConsentMeta | None = None
    if "consent" in header:
        raw = json.loads(header["consent"])
        consent = ConsentMeta(
            tier=str(raw.get("tier", "")),
            declared_by=str(raw.get("declared_by", "")),
            timestamp=str(raw.get("timestamp", "")),
        )

    return SpeakerProfile(
        kv_cache=tensors["kv_cache"],
        sample_rate=int(header.get("sample_rate", SAMPLE_RATE_HZ)),
        source=source,
        watermark_enabled=watermark,
        consent=consent,
    )
