# 07 — Roadmap & Milestone

> **Status**: Final · **Versi**: 1.0 · **Tanggal**: 2026-09-06
> **Kontributor**: `@planner` (penjadwalan), `@writer`
> **Prasyarat baca**: `docs/01-PRD.md` §9 (rilis & acceptance)

---

## 1. Prinsip Penjadwalan

1. **Proof-of-architecture dulu**: M1 membuktikan arsitektur dengan `en` (data publik melimpah), baru ekspansi bahasa.
2. **Keamanan sebelum publik**: rilis publik (beta) hanya setelah threat P0 (T1–T3) mitigated.
3. **Bahasa prioritas pertama**: `id` selesai sebelum `ms`/`jv` dimulai — fokus > sebaran.

## 2. Milestone

### M1 — Core Engine (bulan 1–2)
- **Isi**: Backbone + codec port, streaming decode, CLI `generate`, preset 2 suara `en`, benchmark harness.
- **Deliverable**: `pip install aegisx-tts` (private), generate en bekerja end-to-end.
- **Exit criteria**: RTF en ≤ 0.30 (M4 2-thread), chunk-1 ≤ 300 ms, RAM ≤ 450 MB (angka sementara, pre-optimasi).
- **Terkait**: REQ-001..003 (en dulu), ADR-001/002.

### M2 — Alpha: Bahasa Indonesia (bulan 2–4)
- **Isi**: TN id + G2P rule-based id (docs/02 §3), training pipeline id (docs/03), katalog 4 suara id, CLI lengkap, DVC + W&B.
- **Deliverable**: rilis alpha publik `0.1.0` (id + en), halaman demo sederhana.
- **Exit criteria**: MOS id ≥ 3.4; CER id ≤ 8%; REQ-001..003 lulus di id; docs/06 Gate-Release alpha hijau.
- **Terkait**: F1, F5 (parsial), G2.

### M3 — Server & Integrasi (bulan 4–5)
- **Isi**: FastAPI server + web UI, WS streaming, OpenAI-compat endpoint, watermark implement (keputusan OQ-1), consent flow CLI/server, security headers.
- **Deliverable**: `aegisx-tts serve`, compat suite lulus.
- **Exit criteria**: REQ-030, REQ-060; threat T3/T4/T8 mitigated dengan test.
- **Terkait**: F3, F6, F2 (infra), T1–T3 progress.

### M4 — Beta Publik (bulan 5–7)
- **Isi**: Voice cloning lengkap + consent tiers + watermark verifier CLI; katalog 8 suara id / 6 en; i18n UI (4 bahasa); hardening P0 final; Docker image.
- **Deliverable**: rilis beta `0.5.0` publik + model card draft + security.txt.
- **Exit criteria**: REQ-020..022, REQ-050, REQ-100 lulus; docs/05 §8 checklist ✅ semua; MOS-SIM ≥ 3.5.
- **Terkait**: F2, F5, F10, NFR-10/12.

### M5 — Varian 24L: ms & jv (bulan 7–10)
- **Isi**: Training ms_24l & jv_24l (docs/03 §5.1 S2), leksikon jv (2 dialek), 4 suara per bahasa, register metadata jv, WASM preview (F7).
- **Deliverable**: rilis `0.9.0` dengan 4 bahasa lengkap; editor fonem web komunitas.
- **Exit criteria**: MOS ms ≥ 3.5, jv ≥ 3.4; REQ-040/041; CER ms/jv ≤ 8%.
- **Terkait**: F4, F7 (preview), OQ-2/OQ-3.

### M6 — GA 1.0 (bulan 10–12)
- **Isi**: Audiobook mode (F8), training code publik (F9), audit keamanan eksternal ringan, model card final, dokumentasi lengkap, PyPI promoted.
- **Deliverable**: `1.0.0` — 4 bahasa, cloning etis, server, WASM preview.
- **Exit criteria**: MOS id ≥ 3.8 (G2); seluruh AC PRD lulus; gate-release GA hijau; audit temuan ≥ medium ditutup.
- **Terkait**: F8, F9, G1–G5.

## 3. Timeline Visual

```
Bulan        1   2   3   4   5   6   7   8   9   10  11  12
M1 Core      ████████
M2 Alpha id      ████████████
M3 Server                ████████
M4 Beta                      ████████████
M5 ms+jv                             ████████████████
M6 GA                                        ████████████
```

## 4. Tim Minimal

| Peran | FTE | Fase |
|-------|-----|------|
| ML engineer (model/training) | 2 | M1–M6 |
| Software engineer (server/CLI/SDK) | 1 | M1–M6 |
| Data engineer (kurasi/pipeline) | 1 | M2–M5 |
| Linguist id/jv/ms | 1 (paruh) | M2, M5 |
| Security/etika | 0.5 | M3–M4, M6 |
| Product/community | 0.5 | semua |

## 5. Ketergantungan Kritis

1. **Korpus jv** (docs/03 §3.4) harus kontrak di bulan ke-6 paling lambat, agar training M5 tidak molor.
2. **Keputusan watermark** (OQ-1) harus tuntas di M3 — mengblokir beta.
3. **Lisensi korpus riset** (SARGA/SLC) — verifikasi legal di bulan ke-3.

## 6. Pasca-1.0 (bukan komitmen)

- Varian 300M untuk jv jika kualitas di bawah target.
- SSML `<break>`, register krama jv (OQ-3), emosi ringan via voice prompt.
- Runtime GPU resmi, ONNX/WASM penuh, bahasa komunitas baru (sunda, balinese — program bahasa komunitas).
- ASR pendamping sebagai proyek saudara.
