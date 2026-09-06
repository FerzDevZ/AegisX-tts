# RFC — AegisX-TTS: Arsitektur Sistem & Keputusan Teknis

> **Status**: Final · **Versi**: 1.0 · **Tanggal**: 2026-09-06
> **Penulis**: `@architect` · **Reviewer keamanan**: `@threat-modeler-stride`
> **Referensi**: `docs/00-index.md`, `docs/01-PRD.md`

---

## 1. Ringkasan / Summary

AegisX-TTS adalah sistem TTS (text-to-speech) open-source yang:

1. Berjalan **full di CPU** (tanpa GPU) dengan footprint kecil (≤ 100M parameter base).
2. Menghasilkan audio secara **streaming** dengan latensi chunk pertama ≤ 250 ms.
3. Mendukung **voice cloning** dari sampel audio singkat (≤ 10 detik) atau voice embedding `.safetensors`.
4. Menyediakan **CLI, Python SDK, HTTP server, dan runtime browser (WASM)**.
5. Fokus bahasa: **Indonesia (id)** dan **Inggris (en)** pada base model; **Melayu (ms)** dan **Jawa (jv)** pada varian 24-layer — total 4 bahasa.

## 2. Konteks & Tujuan / Context & Goals

### 2.1 Masalah
- TTS berkualitas tinggi umumnya butuh GPU atau API cloud berbayar.
- TTS open-source untuk **Bahasa Indonesia, Melayu, dan Jawa** nyaris tidak ada yang memenuhi standar kualitas streaming real-time.
- Kebutuhan privasi: sintesis suara harus bisa berjalan lokal (on-device / on-prem).

### 2.2 Non-Goals
- Bukan sistem ASR (speech-to-text).
- Bukan platform hosting model pihak ketiga.
- Tidak menargetkan real-time factor (RTF) di perangkat embedded kelas Cortex-A (ditunda ke versi >1.0).

## 3. Arsitektur High-Level

```
┌─────────────────────────────────────────────────────────────────┐
│                        AEGISX-TTS SYSTEM                        │
│                                                                 │
│  ┌──────────┐   ┌──────────┐   ┌───────────┐   ┌────────────┐  │
│  │  CLI     │   │ Python   │   │ HTTP      │   │ WASM       │  │
│  │ (typer)  │   │ SDK      │   │ Server    │   │ (browser)  │  │
│  └────┬─────┘   └────┬─────┘   │ (FastAPI) │   └─────┬──────┘  │
│       │              │         └────┬──────┘         │         │
│       └──────────────┼──────────────┼────────────────┘         │
│                      ▼              ▼                          │
│             ┌─────────────────────────────┐                    │
│             │      CORE ENGINE (Rust-like │                    │
│             │      boundary di Python)    │                    │
│             │  ┌───────────────────────┐  │                    │
│             │  │ TextNormalizer        │  │  per-language      │
│             │  │  - id, en, ms, jv     │  │  pipeline          │
│             │  │  - G2P (phonemizer)   │  │                    │
│             │  └──────────┬────────────┘  │                    │
│             │             ▼               │                    │
│             │  ┌───────────────────────┐  │                    │
│             │  │ Transformer Backbone  │  │  ~100M params      │
│             │  │  (causal, streaming)  │  │  base / 24L        │
│             │  └──────────┬────────────┘  │                    │
│             │             ▼               │                    │
│             │  ┌───────────────────────┐  │                    │
│             │  │ AudioCodec (RVQ)      │  │  24 kHz mono       │
│             │  │  decoder              │  │                    │
│             │  └──────────┬────────────┘  │                    │
│             └─────────────┼───────────────┘                    │
│                           ▼                                    │
│             ┌─────────────────────────────┐                    │
│             │  VOICE STATE MANAGER        │                    │
│             │  - preset voices            │                    │
│             │  - cloned voices (.wav)     │                    │
│             │  - cached (safetensors)     │                    │
│             └─────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

### 3.1 Komponen Utama

| Komponen | Tanggung jawab | Bahasa/tools | Catatan |
|----------|----------------|--------------|---------|
| `aegisx_tts.core.model` | Transformer backbone + inferensi streaming | Python + PyTorch | Causal attention, batch=1 |
| `aegisx_tts.core.codec` | Audio codec encoder/decoder (RVQ) | Python + PyTorch | 24 kHz mono, frame 80 ms |
| `aegisx_tts.text.normalize` | Normalisasi teks (angka, tanggal, singkatan) per bahasa | Python | 4 modul: id, en, ms, jv |
| `aegisx_tts.text.phonemize` | Grapheme-to-Phoneme | Python + `phonemizer` (espeak-ng backend) + rule fallback | id & jv pakai rule-based; en pakai espeak |
| `aegisx_tts.voice.state` | Voice state manager (preset, clone, cache) | Python | safetensors untuk fast-load |
| `aegisx_tts.server` | HTTP server + Web UI | Python + FastAPI + htmx | Streaming SSE/WS |
| `aegisx_tts.cli` | CLI commands (`generate`, `serve`, `export-voice`) | Python + typer | Subperintah ringkas; flag minim |
| `aegisx_tts.wasm` | Browser runtime (opsional, M5+) | Rust + ONNX Runtime Web → WASM | Kompilasi terpisah |

### 3.2 Keputusan Arsitektur Utama (ADR)

| ID | Keputusan | Alternatif yang ditolak | Alasan |
|----|-----------|------------------------|--------|
| ADR-001 | PyTorch CPU-only sebagai runtime utama | ONNX Runtime, JAX, Candle | Ekosistem matang, tim berpengalaman PyTorch; ONNX Runtime Web dipertahankan untuk jalur WASM |
| ADR-002 | Arsitektur base model: causal Transformer ~100M params + RVQ codec decoder | Diffusion, Flow-matching | Streaming-friendly, CPU-efficient, arus utama riset streaming TTS |
| ADR-003 | Varian 24-layer untuk `ms` & `jv` (bukan base) | Fine-tune dari base 12-layer | Bahasa ber-korpus kecil butuh kapasitas ekstra (lihat docs/02 §2.1) |
| ADR-004 | G2P hybrid: rule-based untuk id/ms/jv, espeak-ng untuk en | espeak-ng untuk semua | espeak-ng tidak akurat untuk jv; rule-based lebih transparan & mudah dikoreksi komunitas |
| ADR-005 | Voice state disimpan sebagai safetensors (KV-cache embedding) | JSON, pickle | Load cepat (<50 ms), portable, aman (bukan arbitrary pickle) |
| ADR-006 | HTTP API kompatibel dengan OpenAI `/v1/audio/speech` | API custom murni | Interop ekosistem (Home Assistant, Discord, dsb.) |
| ADR-007 | Audio watermark (inaudible) di semua output cloning | Tanpa watermark | Mandat etika (lihat docs/05), mencegah deepfake abuse |
| ADR-008 | Model weights dilisensikan CC-BY-4.0, kode Apache-2.0 | Semua MIT | Model turunan data speaker perlu atribusi; kode standar OSS |

## 4. Data Flow

### 4.1 Sintesis Teks → Audio (happy path)

```
input teks (str)
   │
   ▼
[TextNormalizer] ──► teks ternormalisasi (angka→kata, dsb.)
   │
   ▼
[Phonemizer] ──► urutan fonem + token
   │
   ▼
[Backbone.forward_stream] ──► token RVQ per frame (streaming, chunk 80 ms)
   │
   ▼
[CodecDecoder] ──► PCM float32 @24 kHz
   │
   ▼
[Output adapter] ──► WAV / PCM stream / Opus (WS) / tensor Python
```

### 4.2 Voice Cloning

```
audio referensi (≤10 s, .wav/.mp3)
   │
   ▼
[Preprocessing: VAD trim, loudness norm EBU R128, resample 24 kHz]
   │
   ▼
[VoiceEncoder] ──► voice embedding (KV-cache state)
   │
   ├──► dipakai langsung (in-memory)
   └──► save_speaker() → .safetensors (cache portable)
```

## 5. Batas Sistem & Antarmuka

### 5.1 Trust Boundaries (untuk threat model)

| TB | Batas | Contoh |
|----|-------|--------|
| TB1 | User ↔ CLI/SDK | File input `.wav` tidak tepercaya |
| TB2 | Client ↔ HTTP Server | Request API, upload voice sample |
| TB3 | Server ↔ Model Weights | Load config YAML dari URL/HF |
| TB4 | Model ↔ Output | Audio yang dihasilkan (potensi misuse) |

### 5.2 Kontrak Data Kunci

```python
# Speaker profile (kontrak publik SDK)
@dataclass(frozen=True)
class SpeakerProfile:
    kv_cache: torch.Tensor      # [n_layers, seq_len, d_model]
    sample_rate: int            # selalu 24000
    source: SpeakerSource       # PRESET | CLONED | EXPORTED
    watermark_enabled: bool     # True untuk CLONED
```

```yaml
# Config model (YAML)
model:
  backbone: { layers: 24, d_model: 768, heads: 12 }
  codec: { sample_rate: 24000, frame_ms: 80, rvq_levels: 8 }
language: jv
voices:
  - name: begja
    source: hf://aegisx/voices-jv/begja.safetensors
```

## 6. STRIDE Threat Model — Matriks Mitigasi

Dianalisis oleh `@threat-modeler-stride` pada trust boundaries TB1–TB4. Risiko diskor dengan DREAD (1–5).

| # | Threat | Kategori | TB | D-R-E-A-D | Dampak | Mitigasi Wajib | Status |
|---|--------|----------|----|-----------|--------|----------------|--------|
| T1 | Deepfake suara tokoh publik/politik dari cloning | Spoofing (abuse) | TB4 | 5-4-4-5-4 = **22** | Sosial-politik | Watermark inaudible wajib; consent record sebelum export; blacklist query tokoh publik terdaftar | 🔴 P0 |
| T2 | Upload audio tanpa izin pemilik suara | Spoofing | TB2 | 5-4-3-5-3 = **20** | Privasi | Consent flow di `export-voice`; hash audio + metadata consent disimpan; audit log | 🔴 P0 |
| T3 | Model/config YAML dari URL berbahaya (config injection) | Tampering | TB3 | 4-4-5-5-3 = **21** | RCE/DoS | Whitelist domain (hf.co, github.com); hash pinning wajib via `@revision`; sandbox parse YAML (no custom tags) | 🔴 P0 |
| T4 | DoS via teks ekstrem (10 MB teks) ke server | DoS | TB2 | 3-5-4-4-4 = **20** | Availability | Limit teks ≤ 50k char; rate limit per IP; queue dengan max concurrent job | 🟠 P1 |
| T5 | Pickle/cap payload voice berbahaya | Tampering | TB1 | 4-3-4-4-2 = **17** | RCE lokal | Hanya terima safetensors (bukan pickle); validasi schema tensor; error jelas | 🟠 P1 |
| T6 | Pembongkaran watermark → penyalahgunaan tanpa jejak | Repudiation | TB4 | 3-2-3-5-2 = **15** | Akuntabilitas | Watermark redundant + robust terhadap resample/MP3; dokumentasi detektor publik | 🟠 P1 |
| T7 | Voice embedding bocor (privacy leak dari sample asli) | Info Disclosure | TB2 | 4-3-3-4-3 = **17** | Privasi | Embedding disimpan, bukan raw audio; TTL cache server; tidak log teks/audio user | 🟠 P1 |
| T8 | SSRF dari `--config https://...` internal | EoP | TB3 | 3-4-4-3-2 = **16** | Jaringan | Blokir private IP range; timeout & size cap fetch; hanya 3 redirect max | 🟠 P1 |
| T9 | Pencurian voice preset berhak cipta | Repudiation | TB3 | 2-4-3-3-4 = **16** | Legal | Metadata lisensi per voice di config; cek atribusi saat export | 🟡 P2 |
| T10 | Input teks mengandung prompt-injection jika dipakai dalam pipeline LLM | Spoofing | TB1 | 2-3-3-3-3 = **14** | Rendah | TTS hanya mensintesis — tidak mengeksekusi; sanitasi kontrol karakter Unicode | 🟡 P2 |

### 6.1 Rekap Prioritas

- **P0 (harus sebelum rilis publik M4)**: T1, T2, T3 — semua terkait cloning & sumber eksternal.
- **P1 (sebelum M5)**: T4, T5, T6, T7, T8.
- **P2 (backlog)**: T9, T10.

## 7. Deployment Topology

| Mode | Keterangan | Batas sumber daya |
|------|-----------|-------------------|
| **Local CLI** | Satu proses, exit setelah selesai | ~400 MB RAM |
| **Local Server** | FastAPI di localhost:8765 | 1 job konkuren default |
| **Self-hosted (Docker)** | Container, CPU-only image, no CUDA | `--cpus 2`, rate limit aktif |
| **Browser (WASM)** | Semua di client, tanpa server | Model ~200 MB (quantized int8) |

## 8. Performance Budget

| Metrik | Target | Cara ukur |
|--------|--------|-----------|
| RTF (RTF < 1 berarti lebih cepat dari real-time) | ≤ 0.25 (≥4× RT) di M4/Ryzen5, 2 core | benchmark CLI `--bench` |
| Latensi chunk pertama | ≤ 250 ms | Waktu ke byte PCM pertama (streaming) |
| RAM inferensi | ≤ 400 MB | RSS proses |
| Ukuran wheel + weights | wheel ≤ 50 MB; weights base ≤ 220 MB | du pada artifact |
| Load voice dari safetensors | ≤ 50 ms | micro-benchmark |

## 9. Risiko Teknis Non-Keamanan

| Risiko | Kemungkinan | Mitigasi |
|--------|-------------|----------|
| Korpus jv/ms tidak cukup untuk kualitas ≥ 3.5 MOS | Sedang | Data augmentation (speed/tempo perturb), synthetic data dari voice actor (anggaran di docs/03), fallback: perbesar model ke 300M params |
| espeak-ng fonem en tidak natural untuk id-accent | Tinggi | G2P rule-based id sejak M2, bukan espeak |
| Kontribusi komunitas fonem jv lambat | Sedang | Rilis editor fonem web sederhana di M5 |

## 10. Milestone Terkait

Detail timeline di `docs/07-roadmap.md`. Urutan arsitektur:

1. **M1**: Core engine (backbone + codec) bahasa `en` port — bukti arsitektur.
2. **M2**: G2P id + training pipeline id → rilis alpha `id`.
3. **M3**: Server + SDK + kompatibilitas OpenAI API.
4. **M4**: Security hardening P0 (T1–T3) + rilis beta publik.
5. **M5**: Varian 24L `ms` + `jv`, WASM preview.
6. **M6**: Rilis 1.0 + model card + audit eksternal ringan.

## 11. Keputusan Terbuka (Open Questions)

| # | Pertanyaan | Pemilik | Target keputusan |
|---|-----------|---------|------------------|
| OQ-1 | Watermark: pakai library existing (mis. audiosep watermark) atau custom LSB-spectrum? | @ai-engineer | M3 |
| OQ-2 | Apakah varian `jv` perlu data kode etik (unggah-ungguh) sebagai metadata untuk mencegah penggunaan kasar? | @localization-i18n-pro | M5 |
| OQ-3 | Distribusi WASM: bundle model via CDN atau pengguna unduh manual? | @ai-engineer | M5 |
