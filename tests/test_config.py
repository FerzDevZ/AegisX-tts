"""Unit test ModelConfig — konfigurasi model (docs/02 §7).

Aturan kunci:
- Pydantic strict: field tak dikenal → ConfigError (bukan diabaikan).
- sample_rate selalu 24_000; frame_ms selalu 80 (invarian codec docs/02 §4).
- Bahasa harus didukung.
- Config dari URL wajib pin revision `@hash` (mitigasi T3, docs/04 §4.5).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aegisx_tts.core.config import (
    ModelConfig,
    parse_config_dict,
    resolve_config_source,
)

MINIMAL: dict[str, object] = {
    "schema_version": 1,
    "model": {
        "backbone": {"layers": 12, "d_model": 768, "heads": 12, "d_ff": 2560},
        "codec": {"sample_rate": 24000, "frame_ms": 80, "rvq_levels": 8, "codebook_size": 1024},
    },
    "language": "id",
}


class TestParseConfigDict:
    def test_minimal_valid(self) -> None:
        cfg = parse_config_dict(MINIMAL)
        assert cfg.language == "id"
        assert cfg.model.backbone.layers == 12
        assert cfg.watermark.enabled is True  # default fail-closed
        assert cfg.limits.max_text_chars == 50_000  # default docs/02 §7

    def test_field_tak_kenal_ditolak(self) -> None:
        bad = {**MINIMAL, "hoki": True}
        with pytest.raises(Exception, match="hoki"):
            parse_config_dict(bad)

    def test_bahasa_tak_didukung_ditolak(self) -> None:
        bad = {**MINIMAL, "language": "fr"}
        with pytest.raises(Exception, match="language"):
            parse_config_dict(bad)

    def test_sample_rate_bukan_24k_ditolak(self) -> None:
        codec = {"sample_rate": 16000, "frame_ms": 80, "rvq_levels": 8, "codebook_size": 1024}
        bad = {**MINIMAL, "model": {**MINIMAL["model"], "codec": codec}}  # type: ignore[dict-item]
        with pytest.raises(Exception, match="sample_rate"):
            parse_config_dict(bad)

    def test_frame_ms_bukan_80_ditolak(self) -> None:
        codec = {"sample_rate": 24000, "frame_ms": 40, "rvq_levels": 8, "codebook_size": 1024}
        bad = {**MINIMAL, "model": {**MINIMAL["model"], "codec": codec}}  # type: ignore[dict-item]
        with pytest.raises(Exception, match="frame_ms"):
            parse_config_dict(bad)

    def test_voices_wajib_lengkap(self) -> None:
        bad = {**MINIMAL, "voices": [{"name": "siregar"}]}
        with pytest.raises(Exception, match="license|file"):
            parse_config_dict(bad)

    def test_voices_valid(self) -> None:
        voice = {"name": "siregar", "file": "voices/siregar.safetensors", "license": "CC-BY-4.0"}
        cfg = parse_config_dict({**MINIMAL, "voices": [voice]})
        assert cfg.voices[0].name == "siregar"


class TestYamlIO:
    def test_round_trip_yaml(self, tmp_path: Path) -> None:
        import yaml

        path = tmp_path / "id.yaml"
        path.write_text(yaml.safe_dump(MINIMAL), encoding="utf-8")
        cfg = ModelConfig.from_yaml(path)
        assert cfg.language == "id"

    def test_yaml_tidak_ada(self, tmp_path: Path) -> None:
        with pytest.raises(Exception, match="ditemukan"):
            ModelConfig.from_yaml(tmp_path / "hilang.yaml")


class TestResolveSource:
    """Mitigasi T3: URL tanpa pin revision ditolak."""

    def test_local_path_ok(self, tmp_path: Path) -> None:
        src = resolve_config_source(str(tmp_path / "id.yaml"))
        assert src.is_local

    def test_https_tanpa_revision_ditolak(self) -> None:
        with pytest.raises(Exception, match="revision"):
            resolve_config_source("https://example.com/config/id.yaml")

    def test_https_dengan_revision_ok(self) -> None:
        src = resolve_config_source(
            "https://raw.githubusercontent.com/aegisx/models/main/config/id.yaml"
            "@a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        )
        assert not src.is_local
        assert src.revision == "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"

    def test_hf_tanpa_revision_ditolak(self) -> None:
        with pytest.raises(Exception, match="revision"):
            resolve_config_source("hf://aegisx/pocket-tts/config/id.yaml")

    def test_hf_dengan_revision_ok(self) -> None:
        src = resolve_config_source("hf://aegisx/models/config/id.yaml@deadbeef")
        assert src.revision == "deadbeef"

    def test_domain_tak_di_whitelist_ditolak(self) -> None:
        with pytest.raises(Exception, match="whitelist"):
            resolve_config_source(
                "https://evil.example.net/x.yaml@a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
            )
