"""CLI AegisX-TTS — docs/04 §2.

Disiplin output (skill cli-tooling): hasil → stdout, pesan/error → stderr,
exit code jujur (0 sukses; 1 error aplikasi; 2 usage error via typer).
"""

from __future__ import annotations

from pathlib import Path

import torch
import typer

from aegisx_tts import __version__
from aegisx_tts.constants import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from aegisx_tts.errors import AegisXTTSError
from aegisx_tts.text import text_to_tokens

app = typer.Typer(
    name="aegisx-tts",
    help="CPU-first streaming TTS untuk id, en, ms, jv.",
    no_args_is_help=True,
    add_completion=False,
)


def _fail(message: str) -> None:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=1)


def _validate_language(language: str) -> None:
    if language not in SUPPORTED_LANGUAGES:
        _fail(f"Bahasa tidak didukung: {language!r} (didukung: {', '.join(SUPPORTED_LANGUAGES)})")


@app.command()
def generate(
    text: str | None = typer.Option(None, "--text", help="Teks yang akan disintesis."),
    text_file: Path | None = typer.Option(
        None, "--text-file", help="File teks UTF-8 (mutually exclusive dengan --text)."
    ),
    language: str = typer.Option(DEFAULT_LANGUAGE, "--language", help="Kode bahasa: id|en|ms|jv."),
    voice: str = typer.Option("siregar", "--voice", help="Nama preset / path .wav / .safetensors."),
    out: Path = typer.Option("./tts_output.wav", "--out", help="File WAV output."),
    device: str = typer.Option("cpu", "--device", help="Perangkat inferensi: cpu|cuda."),
    quantize: bool = typer.Option(False, "--quantize", help="int8 dynamic quantization (CPU)."),
) -> None:
    """Sintesis teks menjadi suara WAV 24 kHz mono."""
    _validate_language(language)
    if text is None and text_file is None:
        _fail("Wajib menyertakan --text atau --text-file (lihat --help)")
    if text is not None and text_file is not None:
        _fail("--text dan --text-file tidak boleh dipakai bersamaan")
    if device not in ("cpu", "cuda"):
        _fail(f"Device tidak dikenal: {device!r} (pilih: cpu | cuda)")
    if quantize and device == "cuda":
        _fail("--quantize hanya didukung pada device cpu")
    if text_file is not None and not text_file.exists():
        _fail(f"File teks tidak ditemukan: {text_file}")

    # Pipeline teks (L1-L5) sudah aktif di v0.1 — pra-validasi penuh sebelum
    # menyentuh bobot model, sehingga error input terdeteksi di sini.
    content = text if text is not None else (text_file or Path()).read_text(encoding="utf-8")
    try:
        tokens = text_to_tokens(content, language)  # type: ignore[arg-type]
    except AegisXTTSError as exc:
        _fail(str(exc))

    typer.echo(
        f"Pipeline teks OK: {len(tokens)} token. "
        "Sintesis neural menunggu bobot M2 (docs/07 roadmap).",
        err=True,
    )
    raise typer.Exit(code=1)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address (bukan 0.0.0.0)."),
    port: int = typer.Option(8765, "--port", help="Port HTTP+WS."),
    language: str = typer.Option(DEFAULT_LANGUAGE, "--language", help="Bahasa default."),
    quantize: bool = typer.Option(False, "--quantize", help="int8 quantization (CPU)."),
) -> None:
    """Jalankan server HTTP lokal + web UI."""
    _validate_language(language)
    if port < 1 or port > 65535:
        _fail(f"Port tidak valid: {port}")

    import uvicorn

    from aegisx_tts.core.config import ModelConfig

    # Config minimal bawaan; bobot M2 akan di-load di lifespan server.
    config = ModelConfig.from_yaml(
        Path(__file__).parent.parent / "config" / f"{language}.yaml"
    )
    from aegisx_tts.server.app import create_app

    typer.echo(f"AegisX-TTS serve di http://{host}:{port}", err=True)
    uvicorn.run(create_app(config), host=host, port=port, log_level="warning")


@app.command()
def export_voice(
    audio: Path = typer.Argument(..., help="File WAV/MP3 referensi 5–30 detik."),
    out: Path = typer.Argument(..., help="File .safetensors output."),
    consent: str = typer.Option(
        "", "--consent", help="Tier consent: self-declared | written | commercial."
    ),
) -> None:
    """Konversi audio referensi menjadi voice embedding (docs/05 §2)."""
    if not audio.exists():
        _fail(f"File audio tidak ditemukan: {audio}")
    if out.suffix != ".safetensors":
        _fail(f"Output harus .safetensors, dapat: {out.name}")
    if consent and consent not in ("self-declared", "written", "commercial"):
        _fail(f"Tier consent tidak dikenal: {consent!r}")
    _fail("Voice cloning aktif di M2 (docs/07 roadmap); validasi argumen sudah ketat.")


@app.command()
def bench(
    language: str = typer.Option(DEFAULT_LANGUAGE, "--language", help="Bahasa benchmark."),
) -> None:
    """Cetak statistik RTF, latensi chunk-1, RAM peak."""
    _validate_language(language)
    _fail("Benchmark harness aktif di M1 akhir bersama bobot.")


@app.command()
def tokenize(
    text: str = typer.Argument(..., help="Teks untuk pratinjau token pipeline."),
    language: str = typer.Option(DEFAULT_LANGUAGE, "--language", help="Kode bahasa."),
) -> None:
    """Pratinjau pipeline teks: teks → fonem/token (alat debugging)."""
    _validate_language(language)
    try:
        tokens = text_to_tokens(text, language)  # type: ignore[arg-type]
    except AegisXTTSError as exc:
        _fail(str(exc))
    typer.echo(" ".join(tokens))


@app.command()
def verify(
    audio: Path = typer.Argument(..., help="File WAV 24 kHz mono untuk diverifikasi."),
) -> None:
    """Verifikasi watermark konsent dalam file WAV (docs/05 §3)."""
    if not audio.exists():
        _fail(f"File audio tidak ditemukan: {audio}")

    import wave

    import numpy as np

    from aegisx_tts.core.watermark import verify_watermark

    try:
        with wave.open(str(audio), "rb") as w:
            if w.getnchannels() != 1 or w.getsampwidth() != 2:
                _fail("WAV harus mono PCM 16-bit")
            raw = w.readframes(w.getnframes())
    except (wave.Error, EOFError) as exc:
        _fail(f"File bukan WAV yang valid: {exc}")

    ints = np.frombuffer(raw, dtype="<i2")
    audio_tensor = torch.from_numpy(ints.astype(np.float32) / 32768.0)
    payload = verify_watermark(audio_tensor)
    if payload is None:
        _fail("Tidak ada watermark valid terdeteksi dalam audio ini")
        return  # unreachable; _fail selalu raise — membantu type checker

    import json

    typer.echo(
        json.dumps(
            {"tier": payload.tier, "voice": payload.voice},
            ensure_ascii=False,
        )
    )


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"aegisx-tts {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=version_callback, is_eager=True, help="Cetak versi."
    ),
) -> None:
    """AegisX-TTS — CPU-first streaming TTS."""


if __name__ == "__main__":  # pragma: no cover
    app()
