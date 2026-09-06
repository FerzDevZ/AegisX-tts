# 02 — Spesifikasi Teknis: Model, Teks, Audio, Streaming

> **Status**: Final · **Versi**: 1.0 · **Tanggal**: 2026-09-06
> **Kontributor**: `@ai-engineer` (arsitektur model), `@audio-speech-dsp-whisper` (pipeline audio/DSP)
> **Prasyarat baca**: `RFC.md`

---

## 1. Ringkasan

Dokumen ini menjabarkan desain teknis AegisX-TTS di level implementasi: arsitektur model, pipeline teks per bahasa, codec audio, mekanisme streaming, voice state, dan struktur paket Python. Target: engineer yang mengimplementasikan `aegisx-tts` bisa langsung mulai tanpa ambiguitas.

## 2. Arsitektur Model

### 2.1 Komponen Neural

| Komponen | Peran | Ukuran (base) | Ukuran (24L) |
|----------|-------|---------------|--------------|
| `TextEncoder` | Embedding token fonem + positional encoding | 12M | 12M |
| `Backbone` | Causal Transformer, streaming KV-cache | ~70M (12 layer) | ~118M (24 layer) |
| `VoiceEncoder` | Audio referensi → voice embedding (KV-prefix state) | 8M | 8M |
| `CodecDecoder` | Token RVQ → PCM 24 kHz | 10M | 10M |
| **Total** | | **~100M** | **~148M** |

### 2.2 Konfigurasi Backbone

```yaml
backbone:
  layers: 12            # base; 24 untuk varian ms_24l / jv_24l
  d_model: 768
  heads: 12
  d_head: 64
  d_ff: 2560
  dropout: 0.0          # 0 saat inferensi; 0.1 saat training
  norm: rmsnorm
  activation: swiglu
  rope_theta: 10000
  kv_cache: true        # wajib untuk streaming
```

- **Attention**: causal, batch=1, prefill dari voice-prefix state + teks, lalu decode autoregressive per frame audio.
- **Frame audio**: 1 langkah decode ≈ 80 ms audio (lihat §4).

### 2.3 Voice Conditioning

1. Audio referensi 5–10 s → log-mel 24 kHz (hop 320, n_mels 128).
2. `VoiceEncoder` menghasilkan **prefix KV-cache** (per layer): tensor `[n_layers, 2, L_prefix, d_head]` (K dan V terpisah).
3. Prefix digabung dengan KV teks pada prefill → kondisi suara terkunci untuk seluruh generasi.
4. Voice state = prefix KV-cache itu sendiri (disimpan sebagai safetensors) — load speaker ~50 ms karena hanya baca KV dari disk tanpa komputasi.

**Invarian penting**: speaker profile harus di-reuse antar-chunk teks panjang agar suara konsisten (fitur F8). Implementasi: `SpeakerProfile` immutable; generation membuat copy KV untuk teks saja.

## 3. Pipeline Teks (per bahasa)

### 3.1 Tahapan

```
Raw text
  → L1 Unicode sanitize (NFC, buang kontrol char kecuali \n)
  → L2 Sentence split (aturan spesifik bahasa)
  → L3 Normalization (TN): angka, tanggal, mata uang, singkatan
  → L4 G2P (grapheme→phoneme) + stress/tone markers
  → L5 Tokenize fonem + BOS/EOS
```

### 3.2 Aturan Normalisasi `id` (contoh wajib uji)

| Kelas | Input | Output lisan |
|-------|-------|--------------|
| Angka | `2026` | `dua ribu dua puluh enam` |
| Tahun bertanda | `1945` | `seribu sembilan ratus empat puluh lima` |
| Mata uang | `Rp15.000` | `lima belas ribu rupiah` |
| Desimal | `3,14` | `tiga koma satu empat` |
| Tanggal | `17-08-2026` | `tujuh belas Agustus dua ribu dua puluh enam` |
| Jam | `07.30` | `setengah delapan` (konteks informal) / `tujuh tiga puluh` (formal) — default formal |
| Singkatan umum | `sdr.`, `sdri.`, `dll.`, `cth.`, `dsb.` | `saudara`, `saudari`, `dan lain-lain`, `contoh`, `dan sebagainya` |
| Satuan | `5 km`, `10%`, `3 kg` | `lima kilometer`, `sepuluh persen`, `tiga kilogram` |
| Serial | `No. 45` | `nomor empat puluh lima` |

### 3.3 Aturan `ms`, `jv`, `en`

- `ms`: meniru `id` dengan leksikon lokal (`Ringgit Malaysia` untuk RM, jam gaya Melayu, singkatan `sdr.` dsb.).
- `jv`: normalisasi seperti `id` + leksikon jawa (`poen`→`punken` khusus register formal opsional); penanda register `ngoko/krama` berupa metadata per-request (OQ-3), v1 hanya ngoko lughawi.
- `en`: number/date rules standar; singkatan `Mr.`, `Dr.`, `e.g.`; G2P via espeak-ng `en-us`, fallback dict untuk kata umum.

### 3.4 G2P

| Bahasa | Strategi | Rationale |
|--------|----------|-----------|
| `id` | Rule-based ortografi transparan (~40 aturan) + dict pengecualian | Ortografi id sangat fonemik; espeak-ng terlalu "beraksen" |
| `ms` | Port aturan `id` + penyesuaian vokal akhir /ə/ | Kedekatan fonologis |
| `jv` | Rule-based dengan vokal /a/→[ɔ] daerah Solo/Yogya default; dict 10k kata awal | Vokal terbuka bervariasi regional |
| `en` | espeak-ng + dict pengecualian + forced fallback | Standar industri |

- Semua dict pengecualian = file CSV di `aegisx_tts/text/dicts/<lang>.csv`, bisa dikontribusi komunitas (lihat F9).
- Keluaran G2P: deret fonem IPA + boundary marker kata; tokenisasi ke vocab ±512 unit (fonem + marker). Vocab per bahasa di-fix pada rilis model (immutable).

## 4. Codec Audio (RVQ)

```yaml
codec:
  sample_rate: 24000
  frame_ms: 80          # 1 frame = 1920 sampel
  rvq_levels: 8
  codebook_size: 1024
  bandwidth_kbps: ~6.4  # 8 level × 800 bit/s
  mono: true
```

- Encoder hanya dipakai saat training/membuat dataset; inferensi runtime hanya decoder.
- Output decoder: `torch.float32` PCM, rentang [-1, 1], 24 kHz mono.
- Konversi output: WAV (PCM16), raw PCM16, Opus (via `opusenc`/ffmpeg opsi), MP3 (via `lameenc`, opsional).

## 5. Streaming & Latensi

### 5.1 Anggaran Latensi Chunk Pertama (≤ 250 ms)

| Tahap | Budget |
|-------|--------|
| Normalisasi + G2P (teks ≤ 500 char) | ≤ 20 ms |
| Prefill voice-prefix + teks | ≤ 80 ms |
| Decode frame pertama (1 × 80 ms audio) | ≤ 120 ms |
| Overhead queue/IO | ≤ 30 ms |

### 5.2 Strategi Streaming

1. Teks utuh dinormalisasi; jika > 1 kalimat, pecah ke kalimat (F1.3/F8).
2. Decode autoregressive mengalir: setiap frame RVQ selesai → langsung didekode → chunk PCM dikirim ke consumer (callback / WS / file writer).
3. **Crossfade antar-chunk**: 30 ms linear fade untuk menghindari klik (buffer 2 frame).
4. Bila consumer lebih lambat dari produksi (RTF < 1 memungkinkan), buffer membatasi 10 s audio; melebihi → backpressure ke decoder (pause generation).

### 5.3 Perangkat & Quantization

- Default: CPU, `torch.set_num_threads(2)`, int8 dynamic quantization pada Linear (opsi `quantize=True`), memori ≤ 400 MB.
- GPU (best-effort, non-resmi): `.to("cuda")` didukung via API yang sama; tidak ada jaminan RTF lebih baik pada CPU dengan single-thread sangat cepat.
- WASM (F7): export ONNX int8, decoder codec dipindahkan ke kustom op; menyusul M5.

## 6. Struktur Paket Python

```
aegisx_tts/
├── py.typed
├── __init__.py            # Synth, save_speaker
├── core/
│   ├── model.py           # Synth (nn.Module): load, synthesize, stream
│   ├── backbone.py        # Causal transformer + KV cache
│   ├── voice_encoder.py   # audio → prefix KV state
│   └── codec.py           # RVQ decoder
├── text/
│   ├── normalize_id.py / normalize_en.py / normalize_ms.py / normalize_jv.py
│   ├── g2p.py             # dispatcher per bahasa
│   ├── dicts/             # CSV pengecualian per bahasa
│   └── tokenizer.py
├── voice/
│   ├── state.py           # SpeakerProfile dataclass, safetensors IO
│   ├── presets/           # manifest.yaml + .safetensors
│   └── consent.py         # metadata consent (docs/05)
├── server/
│   ├── app.py             # FastAPI, WS, OpenAI-compat
│   └── static/            # web UI (htmx)
├── cli/
│   └── main.py            # typer app: generate, serve, export-voice, bench
├── i18n/
│   └── locales/{id,en,ms,jv}.ftl
└── config/
    ├── id.yaml / en.yaml  # base
    └── ms_24l.yaml / jv_24l.yaml
```

### 6.1 API Inti (kontrak)

```python
class Synth:
    @classmethod
    def load(cls, language: Literal["id", "en", "ms", "jv"],
                   variant: Literal["base", "24l"] = "base",
                   config: str | Path | None = None,
                   quantize: bool = False) -> "Synth": ...

    def speaker_from_preset(self, name: str) -> SpeakerProfile: ...
    def speaker_from_audio(self, path: str | Path) -> SpeakerProfile: ...
    def speaker_from_file(self, path: str | Path) -> SpeakerProfile: ...

    def synthesize(self, speaker: SpeakerProfile, text: str, *,
                   language: str | None = None) -> torch.Tensor: ...

    def stream(self, speaker: SpeakerProfile, text: str, *,
               chunk_ms: int = 80) -> Iterator[torch.Tensor]: ...

def save_speaker(speaker: SpeakerProfile, path: Path, *,
                consent_meta: ConsentMeta | None = None) -> None: ...
```

- `stream` adalah API kanonik; `synthesize` = kumpul semua chunk.
- Semua path publik type-annotated, tanpa `Any` (Gate 1).

## 7. Config Model (YAML)

```yaml
# config/jv_24l.yaml
schema_version: 1
model:
  backbone: { layers: 24, d_model: 768, heads: 12, d_ff: 2560 }
  codec:   { sample_rate: 24000, frame_ms: 80, rvq_levels: 8, codebook_size: 1024 }
language: jv
text:
  g2p: rule_jv
  dict: dicts/jv.csv
voices:
  - { name: begja,  file: voices/begja.safetensors,  license: CC-BY-4.0 }
  - { name: srikaya, file: voices/srikaya.safetensors, license: CC0-1.0 }
watermark:
  enabled: true
  strength: 0.4
limits:
  max_text_chars: 50000
```

- `--config` menerima path lokal, `https://` (whitelist + pin hash — mitigasi T3), atau `hf://repo/path@revision`.
- Validasi schema dengan `pydantic`; field tak dikenal → error (bukan ignore).

## 8. Presisi, Determinisme, Perilaku Edge

| Aspek | Kebijakan |
|-------|-----------|
| Float | fp32 default; bf16 opsional via flag (CPU perf test dulu) |
| Determinisme | Seed fixed saat benchmark; sampling temperature=0 default |
| Teks kosong | `ValueError("Teks kosong")` — exit 2 di CLI |
| Teks > max_chars | CLI: error; Server: HTTP 413 (T4) |
| Karakter tak dikenal | Diganti marker `_unk_`, dicatat warning (bukan silent) |
| Campuran bahasa dalam satu teks | Pipeline bahasa utama; kata asing via dict pengecualian (v1) |

## 9. Benchmark Internal (harus lulus di CI tag rilis)

| Uji | Perangkat | Target |
|-----|-----------|--------|
| RTF base id, teks 5.000 char | M4 2-thread | ≤ 0.25 |
| RTF 24L jv, teks 5.000 char | M4 2-thread | ≤ 0.35 |
| First chunk latency | M4 2-thread | ≤ 250 ms |
| Load voice safetensors | SSD | ≤ 50 ms |
| RAM peak (base) | 2-thread | ≤ 400 MB |

---

*Lanjutan: `docs/03-data-pipeline.md` (data & training), `docs/04-api-spec.md` (kontrak API).*
