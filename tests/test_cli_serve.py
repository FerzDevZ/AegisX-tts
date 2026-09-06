"""Test validasi perintah serve (tanpa benar-benar bind port)."""

from __future__ import annotations

from typing import Any

import pytest

from aegisx_tts.cli.main import app as cli_app

typer_testing: Any = pytest.importorskip("typer.testing")
CliRunner = typer_testing.CliRunner

runner = CliRunner()


def _invoke(*argv: str) -> Any:
    return runner.invoke(cli_app, list(argv))


class TestServeValidation:
    def test_port_di_luar_rentang_ditolak(self) -> None:
        result = _invoke("serve", "--port", "99999")
        assert result.exit_code == 1
        assert "Port" in result.output

    def test_bahasa_tak_didukung_ditolak(self) -> None:
        result = _invoke("serve", "--language", "de")
        assert result.exit_code == 1
        assert "Error" in result.output
