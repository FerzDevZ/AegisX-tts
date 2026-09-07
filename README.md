# AegisX-TTS

[![CI](https://github.com/FerzDevZ/AegisX-tts/actions/workflows/ci.yml/badge.svg)](https://github.com/FerzDevZ/AegisX-tts/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](pyproject.toml)
[![License: Code Apache-2.0 / Weights CC-BY-4.0](https://img.shields.io/badge/license-Apache--2.0_%2B_CC--BY--4.0-green.svg)](#-lisensi--etika)
[![CPU-first](https://img.shields.io/badge/inference-CPU--first-orange.svg)](docs/02-technical-spec.md)

> *TTS ringan yang hidup di CPU-mu — dibangun untuk Bahasa Indonesia, Bahasa Inggris, dan 2 bahasa lainnya (Melayu & Jawa), dengan dukungan full 4 bahasa di seluruh antarmuka.*

**AegisX-TTS** adalah sistem text-to-speech (TTS) open-source yang dirancang dari nol: model ~100M parameter yang berjalan penuh di CPU, streaming real-time dengan latensi chunk pertama ≤ 250 ms, lebih cepat dari real-time, dan mendukung *voice cloning* dari sampel audio singkat.

Repo ini berisi **suite dokumen produk & teknis lengkap** (PRD, RFC, spesifikasi, roadmap) sebagai fondasi sebelum implementasi. Semua dokumen ditulis dwibahasa: **Bahasa Indonesia (utama) + English (sekunder)** pada bagian inti, dan **Melayu (ms) + Jawa (jv)** tersedia untuk dokumen user-facing (README, panduan cepat, UI copy).

---

## 🎯 Target Bahasa

| Kode | Bahasa | Peran | Prioritas |
|------|--------|-------|-----------|
| `id` | Bahasa Indonesia | Bahasa utama model & dokumentasi | P0 |
| `en` | English | Bahasa kedua model, dokumentasi teknis | P0 |
| `ms` | Melayu (Bahasa Melayu) | Bahasa ketiga model (varian 24-layer) | P1 |
| `jv` | Jawa (Basa Jawa) | Bahasa keempat model (varian 24-layer) | P1 |

> 📌 **Catatan**: Jawa dipilih karena jumlah penutur terbesar di Nusantara (~80 juta) namun belum terlayani TTS open-source berkualitas. Melayu dipilih karena kedekatan fonologis dengan Indonesia sehingga transfer learning murah. Keduanya menggunakan arsitektur varian 24-layer (docs/02 §2).

---

## 📚 Struktur Dokumen

| # | Dokumen | Isi |
|---|---------|-----|
| 00 | [docs/00-index.md](docs/00-index.md) | Peta dokumen & panduan membaca |
| 01 | [docs/01-PRD.md](docs/01-PRD.md) | **Product Requirements Document** — visi, target pengguna, fitur, metrics, rilis |
| 02 | [docs/02-technical-spec.md](docs/02-technical-spec.md) | Arsitektur model, tokenisasi teks, pipeline audio, streaming |
| 03 | [docs/03-data-pipeline.md](docs/03-data-pipeline.md) | Sumber data, kurasi, pipeline training per bahasa, lisensi data |
| 04 | [docs/04-api-spec.md](docs/04-api-spec.md) | CLI, Python SDK, HTTP API (OpenAI-compatible), WebRTC/WASM |
| 05 | [docs/05-security-ethics.md](docs/05-security-ethics.md) | Threat model (STRIDE), kebijakan voice cloning, watermark audio |
| 06 | [docs/06-evaluation-qa.md](docs/06-evaluation-qa.md) | Benchmark (MOS, CER/WER), test plan, acceptance criteria |
| 07 | [docs/07-roadmap.md](docs/07-roadmap.md) | Milestone, timeline, rilis |
| 08 | [docs/08-glossary.md](docs/08-glossary.md) | Glosarium istilah (ID/EN) |
| — | [RFC.md](RFC.md) | Decision record arsitektur + trade-off |

---

## 🚀 Quick Start (rencana produk)

```bash
# CLI — generate satu file wav
uvx aegisx-tts generate --language id --voice siregar \
  --text "Halo dunia, ini uji coba AegisX TTS."

# Jalankan server lokal dengan web UI
uvx aegisx-tts serve --language id

# Clone suara dari sampel 10 detik
uvx aegisx-tts export-voice --audio ./saya.wav --out ./suara-saya.safetensors
```

```python
from aegisx_tts import Synth

engine = Synth.load(language="id")
speaker = engine.speaker_from_preset("siregar")  # atau speaker_from_audio(path .wav) / speaker_from_file(path .safetensors)
audio = engine.synthesize(speaker, "Selamat pagi, dunia!")
```

---

## ⚡ Target Non-Fungsional (dari PRD)

- **Ukuran model**: ≤ 100M parameter (base), ≤ 140M (varian 24L)
- **RTF**: ≥ 4× real-time di CPU kelas MacBook Air M4 / Ryzen 5 (2 core)
- **Latensi chunk pertama**: ≤ 250 ms
- **RAM**: ≤ 400 MB saat inferensi
- **CER (id)**: ≤ 6% pada test set internal; MOS ≥ 3.8

---

## 📄 Lisensi & Etika

Model dirilis dengan lisensi permisif (CC-BY-4.0 untuk bobot, Apache-2.0 untuk kode). Voice cloning dibatasi oleh kebijakan etik di [docs/05-security-ethics.md](docs/05-security-ethics.md) — consent record, watermark audio, dan larangan deepfake/political impersonation adalah **hard requirement**, bukan opsional.

---

*AegisX-TTS adalah desain orisinal — seluruh dokumen, kontrak API, dan penamaan dalam repo ini karya mandiri.*
