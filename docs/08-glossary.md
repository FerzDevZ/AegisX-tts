# 08 — Glosarium (ID / EN)

> **Status**: Final · **Versi**: 1.0 · **Tanggal**: 2026-09-06

Istilah teknis yang dipakai di seluruh dokumen AegisX-TTS. Istilah Inggris dipertahankan sesuai konvensi docs/00 §3.

| Istilah | Definisi |
|---------|----------|
| **TTS** (Text-to-Speech) | Teknologi mengubah teks menjadi suara sintetis. |
| **ASR** (Automatic Speech Recognition) | Kebalikan TTS: suara → teks. Dipakai AegisX hanya sebagai alat QA ("ASR-check", docs/06 §2). |
| **RTF** (Real-Time Factor) | Rasio durasi proses terhadap durasi audio hasil. RTF 0.25 = 4× lebih cepat dari real-time. |
| **First-chunk latency** | Waktu hingga byte PCM pertama keluar saat streaming (target ≤ 250 ms). |
| **Voice cloning** | Membuat model berbicara dengan suara dari sampel audio referensi. Di AegisX dikawal consent tiers (docs/05 §2). |
| **Voice state / embedding** | Representasi internal (prefix KV-cache) yang mengkondisikan model pada suara tertentu; disimpan portable sebagai `.safetensors`. |
| **KV-cache / prefix** | Memori attention yang disimpan agar decoding efisien; voice disimpan sebagai prefix KV-cache per layer. |
| **RVQ** (Residual Vector Quantization) | Kodek audio neural berlapis; token RVQ didekode menjadi PCM 24 kHz (docs/02 §4). |
| **PCM** (Pulse-Code Modulation) | Representasi audio digital mentah; AegisX output float32 [-1,1] @ 24 kHz mono. |
| **G2P** (Grapheme-to-Phoneme) | Konversi huruf → fonem. AegisX: rule-based untuk id/ms/jv, espeak-ng untuk en (ADR-004). |
| **TN** (Text Normalization) | Mengubah angka/tanggal/mata uang/singkatan menjadi bentuk lisan (docs/02 §3.2). |
| **Fonem** | Satuan bunyi terkecil pembeda makna. |
| **Ortografi** | Sistem penulisan ejaan suatu bahasa. |
| **CER / WER** | Character/Word Error Rate — ukuran akurasi via ASR round-trip (docs/06 §2). |
| **MOS** (Mean Opinion Score) | Skor naturalness rata-rata dari listener manusia, skala 1–5 (docs/06 §4). |
| **MOS-SIM** | MOS untuk *similarity* suara clone vs. suara asli. |
| **MUSHRA** | Protokol standar uji dengar multi-stimulus; AegisX memakai varian ringan "MUSHRA-lite". |
| **Watermark audio** | Penanda inaudible yang disisipkan pada output cloning untuk deteksi keaslian AegisX (docs/05 §3). |
| **Consent tier** | Tingkat persetujuan pemilik suara: `self-declared` / `written` / `commercial` (docs/05 §2.1). |
| **VAD** (Voice Activity Detection) | Deteksi segmen bersuara; dipakai untuk segmentasi klip dan trim audio referensi (Silero VAD). |
| **Diarization** | Pengelompokan segmen audio per pembicara. |
| **EBU R128 / LUFS** | Standar normalisasi loudness audio (target -23 LUFS di pipeline data). |
| **SNR** (Signal-to-Noise Ratio) | Rasio sinyal terhadap noise; ambang klip ≥ 20 dB. |
| **safetensors** | Format penyimpanan tensor yang aman (bukan pickle), dipakai untuk voice state & bobot. |
| **Streaming / chunking** | Mengirim audio bertahap per frame 80 ms sebelum generasi selesai (docs/02 §5). |
| **Backpressure** | Mekanisme menghentikan generasi saat consumer lebih lambat (> 10 s buffer). |
| **Crossfade** | Penggabungan halus antar-chunk (fade 30 ms) untuk menghindari klik audio. |
| **24L / varian 24-layer** | Varian model 24 layer untuk ms & jv (kapasitas lebih besar, RTF ≤ 0.35) — ADR-003. |
| **Register ngoko / krama** | Level kesantunan bahasa Jawa; v1 hanya ngoko lughawi (docs/05 §6b, OQ-3). |
| **UU PDP** | UU Perlindungan Data Pribadi No. 27/2022 — dasar klasifikasi data suara sebagai data pribadi spesifik. |
| **DVC** (Data Version Control) | Versioning dataset & checkpoint agar training reproducible (docs/03 §5.3). |
| **STRIDE / DREAD** | Kerangka threat modeling & scoring risiko (RFC.md §6). |
| **Trust boundary (TB)** | Batas antar-zona kepercayaan sistem tempat threat dianalisis (RFC.md §5.1). |
| **Fail-closed** | Prinsip: kegagalan kontrol keamanan → tolak operasi (mis. watermark gagal → job gagal). |
| **WASM** (WebAssembly) | Runtime browser untuk model int8 quantized (F7). |
| **Quantization int8** | Kompresi bobot ke 8-bit untuk CPU/WASM. |
| **MoSCoW** | Teknik prioritisasi: Must/Should/Could/Won't (docs/01 §6). |
| **AC** (Acceptance Criteria) | Kriteria penerimaan Given/When/Then (docs/01 §9b). |
| **ADR** (Architecture Decision Record) | Catatan keputusan arsitektur (RFC.md §3.2). |
| **Fluent (.ftl)** | Format file lokalisasi Mozilla, dipakai untuk i18n UI 4 bahasa (docs/04 §7). |
| **Preset voice** | Suara bawaan katalog resmi (mis. `siregar` untuk id), lengkap metadata lisensi. |
