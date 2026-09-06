# 03 — Pipeline Data, Kurasi Korpus & Training

> **Status**: Final · **Versi**: 1.0 · **Tanggal**: 2026-09-06
> **Kontributor**: `@mlops-pipeline-orchestrator` (reproducibility, CT/CD), `@researcher` (sumber data)
> **Prasyarat baca**: `RFC.md`, `docs/02-technical-spec.md`

---

## 1. Ringkasan

Dokumen ini mendefinisikan: target korpus per bahasa, sumber data legal, pipeline kurasi (dari raw audio → klip training), training recipe, tracking eksperimen, dan tata kelola lisensi. Prinsip: **reproducible, versioned, licensed** — setiap dataset dan checkpoint bisa direproduksi dengan satu perintah.

## 2. Target Korpus per Bahasa

| Bahasa | Target jam audio | Rentang durasi klip | Spektrum domain | Prioritas |
|--------|------------------|---------------------|-----------------|-----------|
| `id` | ≥ 300 jam | 3–15 s | 50% konversasional, 25% narasi/berita, 15% audiobook, 10% formal (parlem/berita) | P0 |
| `en` | ≥ 250 jam | 3–15 s | Domain campuran + korpus publik (LibriTTS) | P0 |
| `ms` | ≥ 120 jam | 3–15 s | 60% konversasional, 40% narasi | P1 |
| `jv` | ≥ 150 jam | 3–15 s | 50% konversasional (ngoko), 30% narasi, 20% formal (krama ringan) | P1 |

- Distribusi 50/25/15/10 memastikan model tidak "berbicara berita" saat dipakai konversasional.
- Klip 3–15 s: panjang optimal untuk batch training & voice encoder.

## 3. Sumber Data Legal (per bahasa)

### 3.1 `id`
| Sumber | Jenis | Estimasi | Lisensi/Consent |
|--------|-------|----------|-----------------|
| Common Voice (Mozilla) — id | Crowdsource | ~20 jam | CC0 |
| FLEURS (Google) — id | Read speech | ~10 jam | CC-BY |
| SARGA (UI) | Read speech | ~10 jam | permintaan akses, riset |
| Proyek rekaman mandiri (voice actor) | Studio | 80–120 jam | Kontrak komersial + consent eksplisit |
| Podcast/YouTube berlisensi CC | Konversasional | 60–100 jam | CC-BY/CC0, cek per-episode |
| Corpus parlement id (REMP) | Formal | ~15 jam | public task, atribusi |

### 3.2 `en`
- LibriTTS-R (CC-BY), Common Voice en, podcast CC — korpus publik standar industri.

### 3.3 `ms`
- Common Voice ms, IMDA (Singapore) subset Mandarin+English tidak dipakai; fokus Malaysia/Brunai open corpus, korpus parlem ms (Hansard audio bila tersedia CC), rekaman mandiri 40–60 jam.

### 3.4 `jv`
| Sumber | Jenis | Estimasi | Lisensi |
|--------|-------|----------|---------|
| Common Voice jv | Crowdsource | ~15 jam | CC0 |
| SLC (Speech Corpus of Javanese, riset) | Read+conv | ~25 jam | riset → nego komersial |
| Rekaman mandiri 2 dialek (Solo & Surabaya) | Studio + lapangan | 80–100 jam | Kontrak + consent |
| Radio komunitas CC (Jogja/Solo) | Konversasional | ~20 jam | CC-BY per-episode |

> ⚠️ **Catatan penting**: untuk korpus riset (SARGA, SLC), kualitas untuk training komersial **belum tentu** diizinkan oleh lisensinya. Kebijakan: hanya pakai bila lisensi eksplisit mengizinkan ML training; sisanya hanya untuk evaluasi. Konversi lisensi = tanggung jawab WG hukum (docs/05 §7).

## 4. Pipeline Kurasi

### 4.1 Diagram

```
Raw audio (jam-jaman, bervariasi)
   │
   ├─[A1] Resample ke 24 kHz mono (ffmpeg, sox)
   ├─[A2] Loudness normalize EBU R128 (target -23 LUFS)
   ├─[A3] VAD segmentasi (Silero VAD, min 3 s, max 15 s, pad 200 ms)
   ├─[A4] Denoise opsional (DeepFilterNet2, hanya jika SNR < 15 dB)
   ├─[A5] ASR transkripsi (faster-whisper large-v3, temuan skor)
   ├─[A6] Transkrip murni human (dataset curated) — skip ASR
   │
   ▼
[Transkrip]
   ├─[B1] Case-preserve, tanda baca dinormalisasi
   ├─[B2] Filter kualitas teks: rasio karakter alfanumerik ≥ 0.85
   ├─[B3] Deteksi bahasa (fasttext lid) — buang kontaminasi < 95% bahasa target
   │
   ▼
[Pairing audio↔teks]
   ├─[C1] WER asr-vs-transkrip ≤ 25% → terima; > 25% → buang
   ├─[C2] Rasio durasi/char dalam [60, 120] ms/char → terima; di luar → buang
   ├─[C3] Dedup audio (embedding speaker+content hash)
   │
   ▼
[QC Akhir]
   ├─[D1] SNR ≥ 20 dB (peserta noise floor di bawah -40 dBFS)
   ├─[D2] Clipping: % sampel |x|>0.99 ≤ 0.1%
   ├─[D3] Speaker diarization + embedding — kelompokkan per speaker
   ├─[D4] Sampling rate actual == 24000
   └─[D5] Metadata JSONL: {clip_id, lang, speaker, dur, domain, license, consent_ref}
```

### 4.2 Parameter Pipeline (file `configs/curate.yaml`)

```yaml
audio:
  target_sr: 24000
  loudness: { target_lufs: -23, tp: -1.5 }
  vad: { model: silero, min_dur: 3.0, max_dur: 15.0, pad_ms: 200 }
  denoise_if_snr_below: 15
text:
  min_alpha_ratio: 0.85
  lid_threshold: 0.95
pairing:
  wer_max: 0.25
  ms_per_char: [60, 120]
qc:
  snr_min: 20
  clip_pct_max: 0.1
output:
  format: jsonl
  layout: data/{lang}/{split}/
```

## 5. Training Recipe

### 5.1 Tahap training

| Tahap | Isi | Data | Langkah |
|-------|-----|------|---------|
| S0 | Pretrain codec RVQ pada 2.000 jam campuran (id/en/ms/jv + en publik) | Semua audio | 500k step |
| S1 | Pretrain backbone base (id+en) | id+en kurasi | 400k step |
| S2 | Fine-tune varian 24L ms, jv dari base 24L scratch (atau continue dari base) | ms/jv kurasi | 150k step |
| S3 | Voice encoder training (multi-bahasa) | Semua | 100k step |
| S4 | Alignment/prosody fine-tune ringan (opsional) | narasi | 20k step |

### 5.2 Hyperparameter (base)

```yaml
train:
  precision: bf16
  batch_tokens: 8192        # token per step, bukan klip
  grad_accum: 4
  optimizer: adamw
  lr: 3e-4
  schedule: cosine, warmup 5k
  weight_decay: 0.05
  grad_clip: 1.0
  seed: 20260906
  val_every: 2000 step
  checkpoint_every: 5000 step, keep 3
```

- Hardware: 1 node 8×A100-40GB; base ~4–6 hari; 24L ms/jv ~3–4 hari.
- Fallback jika budget terbatas: skala 100M terbukti dilatih pada 1 node di berbagai proyek komunitas; target RTF CPU tetap.

### 5.3 Tracking & Reproducibility

- **W&B** (primer) + MLflow registry untuk promotion staging→prod.
- **DVC** untuk versioning dataset (`dvc.yaml`: curate → train → eval).
- Setiap checkpoint punya: git SHA, dvc lock, config hash, data fingerprint.
- Gate promotion: eval gate (docs/06 §4) lulus → tag `candidate` → 2 reviewer approve → `prod`.

## 6. Iterasi Kualitas (loop perbaikan)

1. Eval MOS/WER per domain (docs/06).
2. Analisis error terburuk: kumpulkan 100 audio terburuk per bahasa per metrik.
3. Klasifikasi: [pronunciation, prosodi, noise data, kecepatan bicara, lainnya].
4. Perbaikan: tambah data domain lemah (beli/rekam), tambah dict G2P, adjust TN rules.
5. Retrain → eval ulang. Target: MOS naik ≥ 0.1 per iterasi hingga GA.

## 7. Anggaran Data (estimasi)

| Pos | Estimasi | Catatan |
|-----|----------|---------|
| Voice actor id (100 jam studio) | IDR 180–250 jt | 2 pria, 2 wanita, register campur |
| Voice actor jv (60 jam, 2 dialek) | IDR 90–130 jt | Solo + Surabaya, ngoko |
| Voice actor ms (40 jam) | MYR 25–35k | Kuala Lumpur |
| Transkrip/verifikasi manusia | IDR 60 jt | 1.000 jam audio, IDR 60k/jam |
| Compute training (rental 8×A100) | USD 3–6k | bila tidak punya cluster |
| **Total** | **≈ IDR 500–700 jt** | fleksibel; opsi crowdfunding/kolaborasi universitas |

## 8. Lisensi & Tata Kelola Data

- Setiap klip punya `license` + `consent_ref` di metadata (lihat D5). Tanpa itu → klip dibuang.
- Rilis dataset: hanya subset yang lisensinya mengizinkan redistribusi (CC0/CC-BY). Korpus kontrak voice actor dirilis ** sebagai voice preset + embedding**, bukan raw audio.
- `DATA_CAPS.md` mendokumentasikan asal & batas lisensi per sumber — wajib ada sebelum rilis bobot.
- Provenance check CI: job yang memverifikasi setiap klip di manifest punya license field terisi.

## 9. Risiko Data

| Risiko | Mitigasi |
|--------|----------|
| Jumlah jam jv kurang dari target | Augmentasi (speed 0.9/1.1, pitch ±2%), prioritas kualitas > kuantitas; fallback model 300M (pola komunitas korean-300m) |
| Kontaminasi bahasa campur (jv berisi id) | LID threshold 0.95 + review manual 500 sampel acak |
| Speaker overlap train/eval | Split by speaker (bukan klip) — 98/2% klip, 0% speaker overlap |
| Bias gender/dialek | Kuota minimal 30% per gender, 2 dialek jv seimbang |
| Korpus riset tak bisa dipakai komersial | Pisahkan train (legal) vs eval-only; dokumentasi di DATA_CAPS.md |
