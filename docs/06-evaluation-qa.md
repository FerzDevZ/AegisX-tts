# 06 — Evaluasi, Benchmark & QA Plan

> **Status**: Final · **Versi**: 1.0 · **Tanggal**: 2026-09-06
> **Kontributor**: `@researcher` (metodologi evaluasi), `@qa` (test plan), `@llm-evals-judge-benchmarking` (protokol judging)
> **Prasyarat baca**: `docs/01-PRD.md` (REQ IDs, AC), `docs/03-data-pipeline.md` (split data)

---

## 1. Ringkasan

Dokumen ini mendefinisikan cara AegisX-TTS diukur: metrik objektif (CER/WER, RTF), metrik subjektif (MOS, similarity), test set per bahasa, protokol evaluasi manusia, test plan QA perangkat lunak, dan gate rilis. Prinsip: **ukur sebelum klaim** — setiap angka di README/PRD harus punya jalur reproduksi.

## 2. Metrik

| Metrik | Definisi | Alat | Target |
|--------|----------|------|--------|
| CER (id/ms/jv) | Character Error Rate hasil ASR-check: synth → ASR → bandingkan teks asli | faster-whisper large-v3 (id), community ASR ms/jv | ≤ 6% (id), ≤ 8% (ms/jv) |
| WER (en) | Word Error Rate via ASR-check | whisper large-v3 | ≤ 4% |
| MOS (naturalness) | Skala 1–5, listener manusia, min. 20 listener/bahasa | MUSHRA-lite / MOS protokol §4 | ≥ 3.8 (id GA) |
| MOS-SIM (cloning) | Similarity suara clone vs asli, skala 1–5 | AB test protokol §4.3 | ≥ 3.5 |
| RTF | Real-Time Factor = durasi proses / durasi audio | `bench` CLI | ≤ 0.25 base, ≤ 0.35 (24L) |
| First-chunk latency | Waktu → byte PCM pertama | `bench` CLI | ≤ 250 ms |
| RAM peak | RSS proses inferensi | `bench` CLI | ≤ 400 MB |
| Prosody drift (F8) | MOS antar-chunk kontinu vs single-pass | protokol §4.4 | degradasi ≤ 0.2 |

> **Catatan "ASR-check"**: kualitas TTS di-proxy via ASR round-trip. Limitasi dikenali: error ASR ≠ selalu error TTS; angka ASR-check dilaporkan bersama sampel random human-verified 100 klip per bahasa untuk kalibrasi.

## 3. Test Set

### 3.1 Komposisi per bahasa (eval-only, tidak pernah masuk training)

| Set | Isi | Jumlah | Sumber |
|-----|-----|--------|--------|
| `eval-core` | Kalimat seimbang domain (konversasi/narasi/formal), angka+tanggal+mata uang | 500 klip | Kurasi docs/03, split by speaker |
| `eval-tn-stress` | Stress test normalisasi: 200 klip padat angka/ Jam/singkatan | 200 klip | Ditulis manual (F1.3/TN rules) |
| `eval-long` | Teks 5k–50k char (audiobook) | 20 dokumen | Domain publik |
| `eval-clone` | 20 speaker × 2 teks, sampel referensi 10 s | 40 item | Voice actor + CC korpus |
| `eval-adversarial` | Karakter langka, campur bahasa, all-caps, emoji, URL | 100 klip | Manual |

### 3.2 Aturan split
- Split **by speaker**: 0% speaker overlap train/val/eval (docs/03 §9).
- Val 2% klip, eval 2% klip, train sisanya; eval tidak boleh ikut DVC `train.lock`.
- Frozen: setelah rilis alpha, `eval-core` di-frozen (hash di-lock); perubahan = eval versi baru (`eval-core-v2`).

## 4. Protokol Evaluasi Manusia

### 4.1 Panel listener
- **id**: 24 listener di Indonesia, campur usia/gender, kompensasi wajar.
- **ms**: 16 listener (MY); **jv**: 16 listener native (Solo/Surabaya seimbang); **en**: 16 listener.
- Screening: headphone wajib, audisi volume, 1 klip attention-check.

### 4.2 MOS naturalness
- Skala 1–5 (1=buruk, 5=sangat natural), 20 klip/responden/bahasa, random order, dengar penuh sebelum menilai.
- Laporan: mean + 95% CI (bootstrap); klip attention-check gagal → responden dibuang.

### 4.3 MOS-SIM cloning
- AB: sampel asli vs clone, pertanyaan "seberapa mirip suaranya", skala 1–5, 40 item §3.1.

### 4.4 Prosody drift (audiobook)
- Pasangan: chunk ke-n dibacakan single-pass vs audiobook-mode; MOS beda ≤ 0.2 = lulus REQ-080.

### 4.5 Judging tambahan (opsional, non-oficial)
- LLM-judge (mis. audio-LLM) untuk pre-screening murah sebelum eval manusia — hasilnya **tidak** dipakai sebagai klaim publik, hanya sinyal iterasi cepat.

## 5. QA Test Plan (perangkat lunak)

### 5.1 Unit tests (pytest, coverage ≥ 85% `aegisx_tts/text` + `voice`)

| Suite | Cakupan | Contoh kasus |
|-------|---------|--------------|
| `test_normalize_id` | Seluruh tabel docs/02 §3.2 | `Rp15.000` → `lima belas ribu rupiah`; `3,14` → `tiga koma satu empat`; `07.30` → formal |
| `test_normalize_ms_jv` | Leksikon lokal | RM5 → `lima ringgit`; `17-08` tanggal |
| `test_g2p` | Rule + dict pengecualian | kata jawa `/a/→[ɔ]` konteks tertutup; dict override menang |
| `test_speaker_profile` | safetensors IO + consent meta | round-trip load/export; consent tier tersimpan; file korup → error jelas |
| `test_codec` | Frame boundary | chunk 80 ms tepat; resample 24k |
| `test_config` | Pydantic validation | field tak dikenal → error; pin revision wajib untuk URL (T3) |

### 5.2 Integration tests

| Kasus | Verifikasi |
|-------|-----------|
| `generate` end-to-end id (happy path) | WAV valid 24 kHz mono, durasi > 0, RTF tercatat |
| Teks 120k char (AC-4) | Tidak OOM; gap antar-chunk < 200 ms; progress log |
| Server + OpenAI-compat (AC-5, F6) | 422 tanpa `input`; lulus compat suite |
| WS streaming + backpressure | `slow_consumer` error saat pause > 10 s |
| Consent decline (AC-3) | Exit 1, tidak ada file, tidak ada telemetry |
| Config dari URL | Private IP ditolak (T8); domain non-whitelist ditolak (T3) |

### 5.3 Negative & adversarial (wajib min. 2 per fitur — Gate 2)

- Audio referensi 2 s → error `voice_too_short` (AC-7).
- Teks 60k char via server → 413 (AC-8).
- Teks kosong / whitespace → `ValueError` exit 2.
- `.safetensors` pickle-disguise → ditolak (T5).
- Emoji + URL + all-caps → tidak crash, output dinilai di eval-adversarial.
- Voice file dengan consent metadata hilang → output watermark tetap aktif (fail-closed).

### 5.4 Performance & chaos
- `bench` di CI runner bertanda hardware (M4, Ryzen 5500U) — ambang §2.
- Chaos: kill server saat streaming → client dapat WS close bersih, tidak ada hang; disk penuh saat export → error aman, tidak ada partial file.

### 5.5 Accessibility & i18n (web UI)
- axe-core scan: 0 critical violation (WCAG 2.1 AA, NFR-09).
- CI key-parity check .ftl (NFR-11): semua locale ≥ 95% + no missing key.

## 6. Gate Rilis (Dual-Gate mapping)

| Gate | Isi | Wajib lulus untuk |
|------|-----|-------------------|
| **Gate 1 (Static)** | ruff + mypy strict + pip-audit + trivy + secret scan; key-parity i18n; provenance data check (docs/03 §8) | Semua PR |
| **Gate 2 (Behavioral)** | §5.1–5.3 hijau; RTF/latency budget §5.4; min. 1 happy + 2 negative per fitur baru | Semua PR |
| **Gate-Release (QA)** | MOS/MOS-SIM target §2 tercapai; AC PRD semua lulus; checklist docs/05 §8 | Alpha/Beta/GA |

## 7. Laporan Hasil (template)

```markdown
# Eval Report v<versi-model> (tanggal)
## Objektif
| Bahasa | CER/WER | RTF | Latency | RAM |
## Subjektif
| Bahasa | MOS (CI95) | MOS-SIM | n listener |
## Breakdown terburuk
- Top 5 error prononiasi: ... (dict fix: PR #..)
## Keputusan
- [ ] Lulus gate → rilis tag X
- [ ] Tidak lulus → item perbaikan (docs/03 §6 loop)
```

## 8. Risiko Evaluasi

| Risiko | Mitigasi |
|--------|----------|
| ASR-check bias (ASR buruk di jv) | Kalibrasi human-verified 100 klip; laporkan keduanya |
| Listener panel sulit direkrut untuk jv | Kerja sama kampus (Undip/UGM); kompensasi jelas |
| Eval drift antar versi model | eval set frozen + hash lock; perbandingan selalu vs baseline alpha |
| Angka benchmark tidak reproducible | CI runner bertanda hardware; script bench publik |
