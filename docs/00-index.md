# 00 — Peta Dokumen / Document Map

> Status: `v1.0` · Terakhir diperbarui: 2026-09-06 · Pemilik: Product & Architecture WG

Dokumen ini adalah indeks untuk seluruh suite dokumentasi **AegisX-TTS**.

---

## 1. Cara Membaca / How to Read

| Jika kamu adalah... | Baca berurutan |
|---------------------|----------------|
| Investor / manajemen | README → `01-PRD` → `07-roadmap` |
| Engineer (core/model) | `RFC.md` → `02-technical-spec` → `03-data-pipeline` → `06-evaluation-qa` |
| Engineer (platform/API) | `RFC.md` → `04-api-spec` → `05-security-ethics` |
| Data / ML ops | `03-data-pipeline` → `06-evaluation-qa` |
| QA / riset | `06-evaluation-qa` → `01-PRD` |
| Kontributor baru | README → `00-index` → `08-glossary` → bagian yang relevan |

## 2. Daftar Dokumen

| ID | File | Judul | Status | Bahasa |
|----|------|-------|--------|--------|
| 00 | `docs/00-index.md` | Peta dokumen | ✅ Final | id+en |
| 01 | `docs/01-PRD.md` | Product Requirements Document | ✅ Final | id+en |
| 02 | `docs/02-technical-spec.md` | Spesifikasi teknis model & pipeline | ✅ Final | id (en istilah teknis) |
| 03 | `docs/03-data-pipeline.md` | Pipeline data & kurasi korpus | ✅ Final | id |
| 04 | `docs/04-api-spec.md` | CLI, SDK, HTTP API, WASM | ✅ Final | id |
| 05 | `docs/05-security-ethics.md` | Keamanan & etika voice cloning | ✅ Final | id |
| 06 | `docs/06-evaluation-qa.md` | Evaluasi, benchmark, QA | ✅ Final | id |
| 07 | `docs/07-roadmap.md` | Roadmap & milestone | ✅ Final | id |
| 08 | `docs/08-glossary.md` | Glosarium | ✅ Final | id+en |
| — | `RFC.md` | Architecture decision record | ✅ Final | id |

## 3. Konvensi Dokumen

1. **Bahasa**: Dokumen ditulis dalam Bahasa Indonesia; istilah teknis tetap Inggris (mis. *streaming*, *latency*). Bagian PRD dan README diberi paralel English.
2. **Versioning**: Setiap dokumen punya header status (`Draft`, `Review`, `Final`) + tanggal. Perubahan mayor (perubahan requirement/arsitektur) wajib menaikkan versi minor (v1.1 → v2.0).
3. **IDs**: Requirement diberi ID stabil `REQ-XXX`, fitur `F-XX`, milestone `M-XX`. Jangan mengubah ID yang sudah dirilis — tandai `deprecated` saja.
4. **Sumber kebenaran**: Jika dua dokumen bertentangan, urutan kebenaran: `01-PRD` (apa) → `RFC.md` (bagaimana, arsitektur) → `02/03/04` (detail). Ajukan issue untuk rekonsiliasi.
5. **Bahasa model**: `id`, `en` (base, P0) dan `ms`, `jv` (varian 24L, P1). Kode bahasa mengikuti ISO 639-1.

## 4. Dokumen yang Disengaja Tidak Dibuat

- **Perancangan UI mockup** — dibuat saat fase M3 (lihat roadmap), bukan sekarang.
- **Ops runbook produksi** — setelah M4 (deploy awal).
- **Model card final** — saat bobot rilis publik (M6), mengikuti template Hugging Face.

## 5. Bahasa User-Facing (Lokalisasi)

UI web, README, `--help` CLI, dan pesan error dilokalisasi ke 4 bahasa: `id`, `en`, `ms`, `jv`. File terjemahan dikelola di `locales/{id,en,ms,jv}.ftl` (format Fluent). Detail di `04-api-spec.md` §7.
