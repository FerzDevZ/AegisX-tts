"""Unit test CLI (skill cli-tooling: exit code jujur, stdout/stderr terpisah)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from aegisx_tts.cli.main import app as cli_app

typer_testing: Any = pytest.importorskip("typer.testing")
CliRunner = typer_testing.CliRunner

runner = CliRunner()


def _invoke(*argv: str) -> Any:
    return runner.invoke(cli_app, list(argv))


class TestTokenizeCommand:
    def test_happy_path_id(self) -> None:
        result = _invoke("tokenize", "bola", "--language", "id")
        assert result.exit_code == 0
        tokens: Iterator[str] = iter(result.output.split())
        assert next(tokens) == "<bos>"

    def test_bahasa_tak_didukung_exit_1(self) -> None:
        result = _invoke("tokenize", "bola", "--language", "de")
        assert result.exit_code == 1
        assert "Error:" in result.output  # CliRunner menampung stderr ke output

    def test_teks_kosong_exit_1(self) -> None:
        result = _invoke("tokenize", "   ", "--language", "id")
        assert result.exit_code == 1


class TestGenerateCommand:
    def test_tanpa_text_dan_file_ditolak(self) -> None:
        result = _invoke("generate", "--language", "id")
        assert result.exit_code == 1
        assert "--text" in result.output

    def test_text_dan_file_bersamaan_ditolak(self) -> None:
        result = _invoke(
            "generate", "--text", "halo", "--text-file", "x.txt", "--language", "id"
        )
        assert result.exit_code == 1

    def test_bahasa_tak_didukung_ditolak(self) -> None:
        result = _invoke("generate", "--text", "halo", "--language", "de")
        assert result.exit_code == 1

    def test_text_file_hilang_ditolak(self) -> None:
        result = _invoke("generate", "--text-file", "tidak-ada.txt", "--language", "id")
        assert result.exit_code == 1

    def test_quantize_di_cuda_ditolak(self) -> None:
        result = _invoke("generate", "--text", "halo", "--device", "cuda", "--quantize")
        assert result.exit_code == 1

    def test_pipeline_valid_tetap_bobot_belum_rilis(self) -> None:
        result = _invoke("generate", "--text", "halo dunia", "--language", "id")
        # Pipeline teks lulus → progres ke pesan bobot M2, exit 1 dengan pesan eksplisit.
        assert result.exit_code == 1
        assert "M2" in result.output


class TestExportVoiceCommand:
    def test_audio_hilang_ditolak(self, tmp_path: Any) -> None:
        result = _invoke("export-voice", str(tmp_path / "x.wav"), str(tmp_path / "x.safetensors"))
        assert result.exit_code == 1

    def test_ekstensi_output_ditolak(self, tmp_path: Any) -> None:
        src = tmp_path / "a.wav"
        src.write_bytes(b"RIFF")
        result = _invoke("export-voice", str(src), str(tmp_path / "a.pickle"))
        assert result.exit_code == 1

    def test_tier_consent_asal_ditolak(self, tmp_path: Any) -> None:
        src = tmp_path / "a.wav"
        src.write_bytes(b"RIFF")
        result = _invoke(
            "export-voice", str(src), str(tmp_path / "a.safetensors"), "--consent", "gratis"
        )
        assert result.exit_code == 1


class TestVersion:
    def test_version_flag(self) -> None:
        result = _invoke("--version")
        assert result.exit_code == 0
        assert "aegisx-tts" in result.output
