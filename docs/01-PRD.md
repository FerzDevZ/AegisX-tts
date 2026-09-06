# PRD — AegisX-TTS (Product Requirements Document)

> **Status**: Final · **Versi**: 1.0 · **Tanggal**: 2026-09-06 · **Pemilik**: Product WG
> **Fase**: Pre-implementation (dokumen fondasi sebelum kode)

---

# 🇮🇩 BAGIAN 1 — VERSI BAHASA INDONESIA (PRIMER)

## 1. Latar Belakang

Text-to-Speech (TTS) berkualitas tinggi saat ini didominasi dua pola: (a) API cloud berbayar (ElevenLabs, Azure, Google), atau (b) model besar yang menuntut GPU. Belum ada TTS open-source yang memenuhi tiga syarat sekaligus: **berjalan penuh di CPU konsumen, streaming real-time, dan unggul untuk Bahasa Indonesia serta bahasa-bahasa Nusantara**.

Hulu TTS berkualitas tinggi saat ini didominasi dua pola: (a) API cloud berbayar (ElevenLabs, Azure, Google), atau (b) model besar yang menuntut GPU.

## 2. Visi & Misi

**Visi**: Setiap perangkat di Nusantara bisa "bicara" Bahasa Indonesia dan bahasa daerah dengan suara yang natural, tanpa internet, tanpa GPU, tanpa biaya API.

**Misi**: Membangun TTS open-source 100M-parameter CPU-first dengan kualitas streaming real-time untuk `id`, `en`, `ms`, `jv`.

## 3. Tujuan Bisnis & Metrik Keberhasilan

| ID | Tujuan | Metrik | Target | Cara Ukur |
|----|--------|--------|--------|-----------|
| G1 | Adopsi awal developer Indonesia | Jumlah unduhan PyPI/bulan (bulan ke-3) | ≥ 2.000 | Telemetry unduhan PyPI |
| G2 | Kualitas suara id | MOS rata-rata test set internal | ≥ 3.8 | Evaluasi manusia (docs/06) |
| G3 | Kecepatan | RTF ≤ 0.25 di 2 core CPU modern | ≥ 4× real-time | Benchmark `--bench` |
| G4 | Kepercayaan etika | 100% output cloning terwatermark | 100% | Automated scan CI |
| G5 | Komunitas | Kontributor eksternal (bulan ke-6) | ≥ 10 | GitHub insights |

## 4. Target Pengguna & Persona

### Persona 1 — "Raka", Developer Aplikasi Voice Bot WA (id)
- **Konteks**: Membangun chatbot suara WhatsApp untuk UMKM.
- **Masalah**: API cloud mahal (IDR 1–3 per 1k karakter) dan butuh internet.
- **Kebutuhan**: SDK Python sederhana, latensi rendah, biaya nol.
- **Fitur kunci**: F1, F6, F7.

### Persona 2 — "Sinta", Pembuat Konten & Audiobook (id)
- **Konteks**: Produksi audiobook bahasa Indonesia dan Jawa.
- **Masalah**: Narasi multi-karakter butuh banyak suara; kualitas TTS open-source bahasa Indonesia masih kaku.
- **Kebutuhan**: Voice cloning karakter, export batch, teks panjang tak terbatas.
- **Fitur kunci**: F2, F5, F8.

### Persona 3 — "Prof. Bambang", Riset Bahasa (universitas)
- **Usecase**: Riset fonologi jv/ms; butuh model yang bisa di-fine-tune.
- **Fitur kunci**: F9 (training code terbuka), F4 (varian 24L).

### Persona 4 — "Yuki", Developer Home Assistant (en/ms)
- **Usecase**: Smart speaker lokal tanpa cloud.
- **Fitur kunci**: F6 (OpenAI-compatible), F3 (server + WS streaming).

### Tabel Peran → Nilai
| Persona | Nilai utama | Fitur |
|---------|-------------|-------|
| Developer | Integrasi cepat, biaya 0 | F1, F6, F7 |
| Kreator konten | Suara khas, batch, murah | F2, F5, F8 |
| Riset | Transparansi, fine-tune | F4, F9 |
| Smart home | Local-first, interop | F3, F6, F7 |

## 5. Fitur & Persyaratan

### F1 — Sintesis Dasar (id, en)
- **F1.1** `generate` CLI: teks → file WAV 24 kHz mono.
- **F1.2** SDK Python: `Synth.synthesize(speaker, text) -> torch.Tensor`.
- **F1.3** Teks panjang tak terbatas (chunking kalimat otomatis).
- **REQ-001**: RTF ≤ 0.25 pada 2 core CPU modern (M4/Ryzen 5 5500U).
- **REQ-002**: Latensi chunk pertama ≤ 250 ms.
- **REQ-003**: RAM inferensi ≤ 400 MB.

### F2 — Voice Cloning (id, en, ms, jv)
- **F2.1** Clone dari sampel `.wav`/`.mp3` 5–10 detik.
- **F2.2** Export ke `.safetensors` untuk load cepat.
- **F2.3** Flow consent (docs/05) wajib sebelum export.
- **REQ-020**: Cloning quality: MOS similarity ≥ 3.5 vs. sampel asli.
- **REQ-021**: Export-voice: sampel 10 s → embedding ≤ 5 s proses (M4-class CPU).
- **REQ-022**: Watermark inaudible aktif default pada output cloning.

### F3 — Server Lokal + Web UI
- **F3.1** `serve` membuka server di `localhost:8765` dengan web UI sederhana.
- **F3.2** Endpoint REST + WebSocket streaming (PCM chunks).
- **F3.3** Endpoint kompatibel OpenAI `/v1/audio/speech`.
- **REQ-030**: Server siap dalam ≤ 3 s (model load).
- **F3.4** Model tetap di memori antar-request.

### F4 — Varian Bahasa 24-Layer (ms, jv)
- **F4.1** Model varian `ms_24l`, `jv_24l` dengan kapasitas lebih besar (24 layer, d_model 768).
- **F4.2** Seleksi via `--language ms_24l`.
- **REQ-040**: Kualitas `ms_24l` ≥ base `ms` +0.3 MOS.
- **REQ-041**: RTF varian 24L ≤ 0.35 (lebih lambat tapi masih ≥ 2.8× RT).

### F5 — Katalog Suara (voice catalog)
- **F5.1** ≥ 8 suara preset per bahasa (`id`, `en`) dan ≥ 4 suara per bahasa `ms`, `jv`.
- **F5.2** Metadata lisensi per suara (CC0 / CC-BY / hak khusus).
- **F5.3** Suara beragam: gender, usia, register formal/informal.
- **REQ-050**: Setiap preset memiliki metadata `name, lang, gender, age, license, consent_proof`.

### F6 — Kompatibilitas OpenAI API
- **F6.1** `POST /v1/audio/speech` menerima schema OpenAI TTS (model, input, voice, response_format).
- **F6.2** Mendukung `response_format`: wav, pcm, mp3 (via transcode), opus.
- **REQ-060**: Pass seluruh test suite kompatibilitas OpenAI TTS open-source (mis. openai-tts-compat tests).

### F7 — Runtime Browser (WASM, preview)
- **F7.1** Runtime WASM di browser (opsional, preview M5).
- **F7.2** Model quantized int8 (~200 MB) diunduh sekali, cache IndexedDB.
- **REQ-070**: RTF di Chrome desktop ≥ 0.8× real-time.
- **F7.3** Tidak ada data yang keluar dari browser.

### F8 — Sintesis Teks Panjang (audiobook mode)
- **F8.1** Chunking kalimat + konsistensi prosodi antar-chunk.
- **F8.2** Cache voice state antar-chunk untuk konsistensi suara.
- **REQ-080**: Drift prosodi antar-chunk ≤ ambang MOS degradasi 0.2.
- **F8.3** Output: satu WAV per bab, atau folder per-bagian.

### F9 — Training Code Terbuka
- **F9.1** Pipeline training reproducible (DVC + W&B/MLflow).
- **F9.2** Recipe fine-tune bahasa baru (playbook bahasa tambahan).
- **F9.3** Config YAML per bahasa (`config/id.yaml`).
- **training/README.md** menjelaskan cara fine-tune bahasa baru.
- **REQ-090**: Orang luar bisa melatih model bahasa baru tanpa kontak tim.

### F10 — Lokalisasi Antarmuka (id, en, ms, jv)
- **F10.1** UI web, CLI help, dan pesan error dalam 4 bahasa.
- **F10.2** Format Fluent (.ftl), fallback ke `en`.
- **REQ-100**: Cakupan terjemahan ≥ 95% string UI per bahasa.

## 6. Prioritas Fitur (MoSCoW)

| Fitur | Must | Should | Could | Won't (v1) |
|-------|:----:|:------:|:-----:|:----------:|
| F1 Sintesis dasar | ✅ | | | |
| F2 Voice cloning | ✅ | | | |
| F3 Server + Web UI | ✅ | | | |
| F5 Katalog suara | ✅ | | | |
| F10 Lokalisasi UI | ✅ | | | |
| F4 Varian 24L (ms, jv) | | ✅ | | |
| F6 OpenAI-compat | | ✅ | | |
| F8 Audiobook mode | | ✅ | | |
| F9 Training code | | ✅ | | |
| F7 WASM browser | | | ✅ | |
| Jeda via SSML `<break>` | | | | ✅ (v1) |

## 7. Requirement Non-Fungsional

| ID | Kategori | Requirement | Target |
|----|----------|-------------|--------|
| NFR-01 | Performa | RTF | ≤ 0.25 (base), ≤ 0.35 (24L) |
| NFR-02 | Performa | Latensi chunk-1 | ≤ 250 ms |
| NFR-03 | Resource | RAM inferensi | ≤ 400 MB |
| NFR-04 | Resource | CPU | ≤ 2 core aktif |
| NFR-05 | Portabilitas | OS | Linux, macOS, Windows |
| NFR-06 | Portabilitas | Python | 3.10–3.14 |
| NFR-06b | Ukuran | Wheel | ≤ 50 MB |
| NFR-07 | Ukuran | Weights base | ≤ 220 MB |
| NFR-08 | Privasi | Data user | Tidak ada teks/audio user yang keluar dari mesin (mode lokal) |
| NFR-08b | Privasi | Telemetry | Opt-in, anonymized, tanpa teks |
| NFR-09 | Aksesibilitas | Web UI | WCAG 2.1 AA |
| NFR-10 | Keamanan | Threat P0 | Semua mitigasi T1–T3 implement sebelum rilis publik |
| NFR-10b | Keamanan | Dependency scanning | CI punya SAST/dep-scan (pip-audit + trivy) |
| NFR-11 | i18n | Cakupan UI | ≥ 95% per bahasa |
| NFR-12 | Etika | Consent + watermark | 100% output cloning |


## 8. UX & Copy Konkret

### 8.1 Alur `export-voice` (consent flow)
```
$ aegisx-tts export-voice --audio suara-bapak.wav
⚠️  Audio ini akan dikonversi menjadi "voice embedding".
   Pastikan Anda memiliki izin pemilik suara.
   [L]anjut / [b]atal: L
✓ Voice embedding tersimpan: suara-bapak.safetensors  (diproses 3.2 s)
  Metadata consent: "self-declared" (lihat docs/05 §3)
```

### 8.2 Web UI (M3)
- Panel kiri: teks input, pilih bahasa & suara, tombol **Bicara**.
- Panel kanan: player + waveform + tombol unduh.
- Toggle "Mode privasi penuh" (tanpa telemetry sama sekali).

## 9. Rilis & Kriteria Acceptance

| Rilis | Isi | Kriteria keluar |
|-------|-----|-----------------|
| **Alpha (M2)** | F1 id, en + CLI | REQ-001..003 lulus; MOS id ≥ 3.4 |
| **Beta (M4)** | +F2, F3, F5, F10 | + REQ-020..022, 030, 050, 100; threat P0 mitigated |
| **GA 1.0 (M6)** | +F4, F6, F8, F9 | + REQ-040, 041, 060, 080, 090; MOS id ≥ 3.8 |

## 9b. Acceptance Criteria Terperinci (Given/When/Then)

**AC-1 (REQ-001, happy path)**
- Given: model `id` sudah ter-load
- When: `generate --text "Selamat pagi" --voice siregar`
- Then: WAV 24 kHz mono valid; RTF ≤ 0.25; chunk pertama ≤ 250 ms

**AC-2 (REQ-021, edge)**
- Given: file `suara.wav` 10 s valid
- When: `export-voice --audio suara.wav`
- Then: `.safetensors` valid; waktu proses ≤ 5 s

**AC-3 (F2.3 + T2, negative)**
- Given: user menekan `[b]atal` di consent prompt
- When: proses export berjalan
- Then: tidak ada file embedding yang ditulis; exit code 1; tidak ada telemetry terkirim

**AC-4 (F1.3, edge)**
- Given: teks 120k karakter
- When: `generate --text-file buku.txt`
- Then: proses selesai tanpa OOM (RAM ≤ 400 MB); durasi WAV = total durasi per-chunk; tidak ada gap ≥ 200 ms antar-chunk yang tidak disengaja; progress log per-chunk (n/total) tampil

**AC-5 (F6, negative)**
- Given: server berjalan
- When: `POST /v1/audio/speech` tanpa field `input`
- Then: HTTP 422 dengan pesan validasi sesuai bahasa header `Accept-Language`

**AC-6 (NFR-11, i18n)**
- Given: `LANG=jv_ID.UTF-8`
- When: CLI `--help`
- Help jv ditampilkan ≥ 95% string terjemahan jv

**AC-7 (F2.1, edge)**
- Given: audio referensi 2 detik (di bawah minimum 5 s)
- When: `export-voice`
- Then: error jelas: "Sampel minimal 5 detik, terdeteksi 2.0 s" (locale-aware), exit code 2

**AC-8 (T4, negative)**
- Given: server berjalan
- When: input teks 60k karakter
- Then: server menolak dengan HTTP 413, pesan "Teks maksimal 50.000 karakter" (locale-aware)

## 10. Metrik Produk Pasca-Rilis

| Metrik | Target | Sumber |
|--------|--------|--------|
| Retensi mingguan pengguna CLI | ≥ 25% | Telemetry opt-in |
| Error rate per 1k generate | < 2% | Telemetry opt-in + GitHub issues |
| Issue pertama respon < 48 jam | ≥ 90% | GitHub |
| NPS (survey komunitas) | ≥ 40 | Survey rilis 1.0 |

## 11. Ketergantungan & Asumsi

**Asumsi**:
1. Korpus id ≥ 300 jam, ms ≥ 120 jam, jv ≥ 150 jam cukup untuk kualitas target (lihat docs/03).
2. Arsitektur Transformer causal + RVQ codec dapat direplikasi dengan PyTorch CPU.
3. Komunitas fonem jv bisa direkrut via komunitas linguistik (KBBI, Pusat Bahasa, kampus).

**Dependensi eksternal**:
- PyTorch ≥ 2.5 CPU wheels.
- espeak-ng (en) — optional dep.
- safetensors, FastAPI, typer, soundfile.

## 12. Risiko Produk

| Risiko | Kemungkinan | Dampak | Mitigasi |
|--------|-------------|--------|----------|
| MOS id < 3.8 saat GA | Sedang | Tinggi | Iterasi data (docs/03 §6), tambah jam data; fallback target 3.6 + roadmap v1.1 |
| Voice cloning disalahgunakan (deepfake) | Sedang | Tinggi | docs/05: watermark, consent, blacklist; respons insiden 48 jam |
| Kompetitor umum menambah dukungan id | Sedang | Sedang | Diferensiasi: G2P rule-based id, bahasa jv/ms, komunitas Indonesia |
| Kurangnya voice actor jv bersedia | Sedang | Sedang | Bayar voice actor (anggaran docs/03 §7); opsi sintetis dari voice terbatas |

## 13. Out of Scope (v1)

- ASR (speech-to-text) — bisa jadi produk terpisah.
- Emosi/acting control via tag.
- SSML penuh (hanya `<break>` ditunda ke v1 juga).
- Multispeaker simultan dalam satu request.
- TTS server multi-tenant SaaS.
- Bahasa lain di luar id/en/ms/jv (via program komunitas).

## 14. Keputusan Terbuka Produk

| # | Pertanyaan | Pemilik | Target |
|---|-----------|---------|--------|
| PQ-1 | Nama preset voice id — pakai nama daerah (Siregar, Kartini...)? | @writer | M2 |
| PQ-2 | Harga komersial jika ada "support tier"? | Product WG | M5 |
| PQ-3 | Apakah `jv` perlu mode "ngoko/krama" register switch? | @localization-i18n-pro | M5 |

---

# 🇬🇧 PART 2 — ENGLISH VERSION (SECONDARY)

## 1. Background

High-quality TTS today is dominated by paid cloud APIs or GPU-hungry models. No open-source TTS simultaneously offers **CPU-only real-time streaming**, **voice cloning**, and **Indonesian/Malay/Javanese excellence**. AegisX-TTS is designed from the ground up to fill that gap with `id` as the primary language, `en` as secondary, plus `ms` and `jv` 24-layer variants.

## 2. Vision
Every device in the Nusantara archipelago can speak Indonesian and regional languages naturally — offline, CPU-only, at zero marginal cost.

## 3. Goals & Success Metrics
Identical to Part 1 §3 (G1–G5): 2,000+ monthly PyPI downloads by month 3, MOS ≥ 3.8 for `id`, RTF ≤ 0.25, 100% watermarked cloning output, 10+ external contributors by month 6.

## 4. Target Users
Same four personas (developer, content creator/audiobook maker, language researcher, smart-home developer) — see Part 1 §4 for full descriptions and feature mapping.

## 5. Features (English summary)

- **F1 Basic synthesis (id, en)**: CLI `generate`, Python SDK, unbounded text via automatic sentence chunking. RTF ≤ 0.25, first-chunk latency ≤ 250 ms, RAM ≤ 400 MB.
- **F2 Voice cloning (all 4 languages)**: 5–10 s reference audio, `.safetensors` export, mandatory consent flow, inaudible watermark by default.
- **F3 Local server + web UI**: FastAPI, REST + WebSocket PCM streaming, OpenAI-compatible endpoint, model warm in memory.
- **F4 24-layer language variants (ms, jv)**: larger-capacity variants selected via `--language ms_24l`.
- **F5 Voice catalog**: ≥ 8 presets per `id`/`en`, ≥ 4 per `ms`/`jv`, per-voice license metadata.
- **F6 OpenAI API compatibility**: `POST /v1/audio/speech` with wav/pcm/mp3/opus output.
- **F7 Browser runtime (WASM preview)**: int8-quantized model, no data leaves the browser.
- **F8 Audiobook mode**: sentence chunking, prosody consistency across chunks, per-chapter output.
- **F9 Open training code**: reproducible pipelines, language-extension recipe, community-trained models welcome.
- **F10 Localized UI (id, en, ms, jv)**: Fluent `.ftl` files, ≥ 95% coverage per language.

## 6. Non-Functional Requirements
See Part 1 §7 (NFR-01 … NFR-12): performance budgets (RTF, latency, RAM), portability (Linux/macOS/Windows, Python 3.10–3.14), privacy (local-first, opt-in telemetry), WCAG 2.1 AA, security gates (STRIDE P0 mitigations before public release), i18n coverage, and mandatory consent + watermarking.

## 7. Releases & Acceptance
- **Alpha (M2)**: F1 for id+en; REQ-001..003 pass; id MOS ≥ 3.4.
- **Beta (M4)**: + F2, F3, F5, F10; STRIDE P0 mitigations in place.
- **GA 1.0 (M6)**: + F4, F6, F8, F9; id MOS ≥ 3.8.

## 8. Out of Scope (v1)
ASR, emotion/acting control tags, full SSML, simultaneous multi-speaker synthesis in one request, multi-tenant SaaS serving, languages beyond id/en/ms/jv (community-tractable later).

---

*Dokumen ini adalah produk kerja `@writer` sub-agent, direview oleh `@reviewer` pada Phase 3 (verifikasi konsistensi AC ↔ REQ).*
