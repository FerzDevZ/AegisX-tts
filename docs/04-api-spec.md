# 04 — Spesifikasi API: CLI, SDK, HTTP, Streaming, i18n

> **Status**: Final · **Versi**: 1.0 · **Tanggal**: 2026-09-06
> **Kontributor**: `@audio-speech-dsp-whisper` (audio streaming), `@localization-i18n-pro` (i18n), `@programmer` (kontrak)
> **Prasyarat baca**: `RFC.md`, `docs/02-technical-spec.md`

---

## 1. Ringkasan

Dokumen ini mendefinisikan semua antarmuka eksternal AegisX-TTS: CLI, Python SDK, HTTP API (termasuk kompatibilitas OpenAI), WebSocket streaming, dan kerangka i18n untuk 4 bahasa antarmuka.

## 2. CLI

### 2.1 Struktur Perintah

```
aegisx-tts generate   [--text | --text-file] [--voice] [--language] [--out] [--config] [--device] [--quantize] [--bench]
aegisx-tts serve      [--host] [--port] [--language] [--config] [--quantize]
aegisx-tts export-voice [--audio] [--out] [--consent] [--config]
aegisx-tts bench      [--language] [--text-file] [--runs]
```

### 2.2 `generate`

```
aegisx-tts generate --language id --voice siregar \
  --text "Halo dunia, ini uji coba AegisX TTS." --out out.wav
```

| Opsi | Tipe | Default | Keterangan |
|------|------|---------|------------|
| `--text` | str | — | Teks langsung (mutually exclusive dengan `--text-file`) |
| `--text-file` | Path | — | File teks (UTF-8) |
| `--voice` | str | `siregar` (id), `wren` (en) | Nama preset / path .wav / path .safetensors |
| `--language` | str | `id` | `id`, `en`, `id_24l` tidak ada — base id; `ms`, `jv` (24L otomatis) |
| `--out` | Path | `./tts_output.wav` | Output WAV PCM16 |
| `--config` | str | — | Path/URL/HF config model |
| `--device` | str | `cpu` | `cpu` / `cuda` (best-effort) |
| `--quantize` | flag | off | int8 dynamic quantization (CPU only) |
| `--bench` | flag | off | Cetak statistik RTF, latensi, RAM |

### 2.3 `serve`

```
aegisx-tts serve --language id --port 8765
```

| Opsi | Tipe | Default | Keterangan |
|------|------|---------|------------|
| `--host` | str | `127.0.0.1` | Bind address. Default bukan 0.0.0.0 (mitigasi T4/T8) |
| `--port` | int | 8765 | Port HTTP+WS |
| `--language` | str | `id` | Bahasa default |
| `--config` | str | — | Config model eksternal |
| `--quantize` | flag | off | int8 quantization CPU-only |

### 2.4 `export-voice`

```
aegisx-tts export-voice --audio suara-bapak.wav --out suara-bapak.safetensors --consent self-declared
```

| Opsi | Tipe | Default | Keterangan |
|------|---|---------|------------|
| `--audio` | Path | — | WAV/MP3 5–10 s (5 s min, 30 s max, di-trim VAD ke 10 s) |
| `--out` | Path | `<nama-audio>.safetensors` | File output |
| `--consent` | str | prompt interaktif | `self-declared` / `written` / `commercial` — lihat docs/05 §3 |
| `--config` | str | — | Config model |

### 2.5 `bench`

Cetak statistik RTF, latensi chunk-1, RAM peak per bahasa yang diinstal. Dipakai CI gate release (docs/06 §6).

## 3. Python SDK

### 3.1 Contoh Penggunaan

```python
from aegisx_tts import Synth, save_speaker

engine = Synth.load(language="id", quantize=False)
speaker = engine.speaker_from_preset("siregar")       # preset
audio = engine.synthesize(speaker, "Selamat pagi, dunia!")
# audio: torch.Tensor float32 [-1,1] @ 24kHz mono

# Streaming
for chunk in engine.stream(speaker, "Teks panjang...", chunk_ms=80):
    play(chunk)  # buffer audio player

# Cloning + export
profile = engine.speaker_from_audio("./referensi.wav")
save_speaker(profile, "./suara.safetensors")
```

### 3.2 Sifat API

- `Synth.load()` dan pembuatan speaker = operasi lambat → keep in memory.
- `stream` = API kanonik; `synthesize` = aggregate.
- Semua fungsi publik type-annotated; py.typed tersedia.
- Thread-safety: `Synth` **not thread-safe** untuk sintesis bersamaan; gunakan satu instance per thread (atau lock).

## 4. HTTP API

### 4.1 Endpoint Daftar

| Method | Path | Fungsi |
|--------|------|--------|
| GET | `/` | Web UI (htmx) |
| GET | `/health` | Liveness (200, no auth) |
| GET | `/v1/voices?language=id` | Daftar suara + metadata lisensi |
| POST | `/v1/audio/speech` | Sintesis (OpenAI-compatible) |
| POST | `/v1/audio/speech/stream` | Streaming PCM chunks via SSE |
| WS | `/v1/audio/speech/ws` | Streaming dua arah |
| GET | `/v1/metrics` | Prometheus metrics (opt-in) |

### 4.2 `POST /v1/audio/speech` (OpenAI-compatible)

**Request**
```json
{
  "model": "aegisx-tts-1",
  "input": "Selamat pagi, dunia!",
  "voice": "siregar",
  "language": "id",
  "response_format": "wav"
}
```

**Response**: binary audio (`audio/wav`, `audio/pcm`, `audio/mpeg`, `audio/opus`), header `X-AegisX-Watermark: active|disabled` (selalu `active` pada voice cloned).

**Error schema** (dipakai semua endpoint):
```json
{ "error": { "code": "text_too_long", "message": "Teks maksimal 50.000 karakter", "locale": "id" } }
```

### 4.3 SSE/WS Streaming Protokol

SSE event types: `meta` (sample_rate, format, voice, watermark), `audio` (base64 PCM16), `done`, `error`.
WS messages (JSON): `{"type":"meta"|"audio"|"done"|"error", ...}`.

**Backpressure**: jika consumer lebih lambat 10 s audio, generation di-pause; consumer lari jauh → kirim `error: slow_consumer`.

### 4.4 Rate Limiting & Batas

| Batas | Nilai | Header |
|-------|-------|--------|
| Teks | ≤ 50.000 char | — |
| Audio referensi upload | ≤ 30 s / 5 MB | — |
| Rate | 60 req/menit/IP (server lokal: off default) | `X-RateLimit-*` |
| Konkurensi | 2 generate paralel default | queue 429 ketika penuh |

### 4.5 Security Headers (mitigasi T2/T3/T4/T8)

- `Content-Security-Policy: default-src 'self'` (web UI)
- Upload audio divalidasi magic bytes + durasi via ffprobe sandbox.
- Config URL fetch: whitelist `huggingface.co`, `raw.githubusercontent.com`, pin revision wajib (T3), blokir private IP (T8).
- Tidak ada logging isi teks/audio user (NFR-08) — hanya hash + length.

## 5. Error Semantics

| Kode | HTTP | Situasi |
|------|------|---------|
| `text_too_long` | 413 | teks > 50k char |
| `invalid_voice` | 404 | preset tak dikenal / file tak valid |
| `consent_required` | 422 | export tanpa consent flag/prompt declined |
| `slow_consumer` | 408 (WS close) | backpressure melebihi 10 s |
| `model_not_loaded` | 503 | server masih loading |
| `rate_limited` | 429 | melebihi rate limit |
| `invalid_config` | 500 | config YAML gagal validasi |
| `voice_too_short` | 422 | referensi < 5 s |

## 6. WASM Preview (F7)

- Distribusi: `@aegisx/tts-wasm` npm package + CDN; model int8 diunduh dari HF, cache IndexedDB.
- API JS mirror SDK Python: `Synth.load({language, modelUrl})`, `engine.stream(text, speaker)`.
- RTF target Chrome desktop ≥ 0.8× (REQ-070).

## 7. i18n Framework (F10)

### 7.1 File Fluent

```fluent
# locales/id.ftl
generate-help = Sintesis teks menjadi suara WAV.
export-voice-warn = Audio ini akan dikonversi menjadi voice embedding. Pastikan Anda memiliki izin pemilik suara.
error-text-too-long = Teks maksimal { $limit } karakter.
```

```fluent
# locales/jv.ftl
generate-help = Ngedadekake teks dadi swara WAV.
export-voice-warn = Audio iki bakal diowahi dadi voice embedding. Priesten sampeyan nduweni idin saka sing duwe swara.
error-text-too-long = Teks maksimal { $limit } aksara.
```

### 7.2 Aturan

- Locale dari `--locale` flag > env `LC_ALL` > fallback `en`.
- Cakupan ≥ 95% string per bahasa (NFR-11); CI checks key parity antar file .ftl.
- `jv` pakai register ngoko lughawi untuk UI (formal/krama ditunda — OQ-3).
- Angka & tanggal via ICU MessageFormat.

## 8. Versioning & Deprecation

- API server: prefix `/v1/`; perubahan breaking → `/v2/` + deprecation window 6 bulan.
- SDK: SemVer; breaking di major.
- CLI: flag dihapus hanya di major release; sebelumnya → warning.

---

*Lanjutan: `docs/05-security-ethics.md` (consent & watermark), `docs/06-evaluation-qa.md` (acceptance test).*
