# 05 — Keamanan & Etika: Voice Cloning, Watermark, Threat Mitigasi

> **Status**: Final · **Versi**: 1.0 · **Tanggal**: 2026-09-06
> **Kontributor**: `@security` + `@localization-i18n-pro` (konteks budaya), `@threat-modeler-stride` (matriks di RFC.md §6)
> **Prasyarat baca**: `RFC.md` §6 (STRIDE), `docs/01-PRD.md` (F2, NFR-12)

---

## 1. Prinsip

1. **Cloning bukan fitur bebas** — adalah fitur berisiko tinggi yang dikawal proses.
2. **Privacy by default**: mode lokal tidak mengirim teks/audio keluar mesin (NFR-08).
3. **Kepatuhan hukum Indonesia**: UU PDP No. 27/2022 (perlindungan data pribadi, termasuk data biometrik suara), UU ITE, dan pasal-hak atas nama baik; UU Hak Cipta No. 28/2014 untuk suara sebagai bagian performa.
4. **Etika di atas legalitas**: yang legal belum tentu etis — blacklist tokoh publik berlaku bahkan bila tidak ada larangan hukum eksplisit.

## 2. Kebijakan Voice Cloning

### 2.1 Consent tiers

| Tier | Kode | Bukti minimal | Boleh dipakai untuk |
|------|------|---------------|---------------------|
| T1 | `self-declared` | Deklarasi pengguna di prompt export (log hash + timestamp) | Penggunaan pribadi/non-komersial |
| T2 | `written` | File consent ber-TT digital / PDF / rekaman verbal | Komersial terbatas |
| T3 | `commercial` | Kontrak lisensi suara + identitas terverifikasi | Komersial penuh |

- Metadata tier disimpan **di dalam** file `.safetensors` (header metadata, bukan file terpisah).
- Export tanpa consent → error `consent_required` (docs/04 §5).
- Output watermark **aktif default** di tier T1/T2; hanya T3 (kontrak) yang bisa menonaktifkan via API dengan audit log.

### 2.2 Larangan penggunaan (hard bans)

- Impersonasi tokoh publik/politik (deepfake), termasuk "parodi" tanpa label AI.
- Penipuan (mis. "suara keluarga minta transfer"), berbasis UU ITE pasal 27/28.
- Komersialisasi suara tanpa tier T2/T3.
- Deteksi pasif: daftar blacklist nama tokoh publik tidak reliable — mitigasi utama tetap watermark + consent + respons insiden. Blacklist query bersifat lapisan tambahan untuk preset resmi.

### 2.3 Alur penolakan

```
export-voice --audio x.wav
  → VAD trim → cek durasi ≥ 5 s
  → prompt consent (T1 default)
  → [b]atal → exit 1, tidak ada file ditulis, tidak ada telemetry
  → [L]anjut → embed + watermark metadata tier
```

## 3. Watermark Audio

| Aspek | Keputusan |
|-------|-----------|
| Teknik | Embedding spektral inaudible (psikoakustik) — OQ-1: library existing vs custom, keputusan M3 |
| Daya tahan | Bertahan resample, MP3 128 kbps, loudness norm; TIDAK dijamin bertahan heavy time-stretch |
| Detektor | Public verifier CLI `aegisx-tts verify --audio x.wav` (M4) |
| Scope | Semua output dengan voice `CLONED` (T1/T2); preset resmi boleh non-watermark |
| Kegagalan | Jika watermark gagal embed → job gagal (fail-closed), bukan output tanpa watermark |

## 4. Kepatuhan UU PDP & Klasifikasi Data

| Data | Klasifikasi UU PDP | Penanganan |
|------|--------------------|------------|
| Sampel audio suara | Data pribadi spesifik (biometrik) | Tidak disimpan server; embedding + consent meta saja; TTL cache 1 jam |
| Voice embedding | Turunan biometrik | Diperlakukan sama seperti audio asli |
| Teks input user | Data pribadi bila mengandung PII | Tidak di-log (hanya hash + length) |
| Telemetry | Non-PII, opt-in | Anonymized, agregat |

## 5. Model Card (ringkas, final di M6)

- **Intended use**: sintesis suara id/en/ms/jv, aksesibilitas, audiobook, aplikasi lokal.
- **Out-of-scope use**: impersonasi, deepfake, penipuan, kontrol emosi khusus (v1).
- **Known limitation**: register krama jv terbatas; angka seribu-lima; akun paper reading.
- **Eval**: MOS/WER/CER per bahasa (docs/06), hasil dilaporkan jujur per domain.
- **Provenance data**: ringkasan DATA_CAPS.md (docs/03 §8).

## 6. Respons Insiden

| Skenario | SLA | Aksi |
|----------|-----|------|
| Laporan deepfake berbasis AegisX | 48 jam verifikasi | Deteksi watermark → konfirmasi → publikasi bukti + support takedown |
| Voice preset bocor ke abuse | 72 jam | Revoke preset dari katalog resmi |
| Vuln keamanan (privilege/SSRF) | 72 jam patch | security.txt + advisory |

## 6b. Konteks Budaya & Bahasa (catatan @localization-i18n-pro)

- **jv**: register `krama` (halus) adalah alat kesantunan budaya. Model v1 hanya ngoko; **wajib** dilarang konfigurasi model jv untuk menyuarakan konten SARA/kata kasar dalam register krama — kombinasi yang sangat ofensif secara budaya. Implementasi: blocklist konten + register metadata.
- **ms/id**: hormat bahasa resmi Pusat Bahasa (KBBI/EYD V) untuk normalisasi resmi; variasi lokal tidak "dikoreksi" — didukung via dict pengecualian.
- Semua contoh dokumen memakai nama netral gender dan menghindari stereotip (persona docs/01 §4).

## 7. Tata Kelola & Peran

| Peran | Tanggung jawab |
|-------|----------------|
| Data WG (docs/03) | Lisensi klip, consent_ref, DATA_CAPS.md |
| Model WG | Watermark implement + fail-closed |
| Legal advisor | Review kontrak voice actor, UU PDP mapping |
| Community WG | Moderasi preset komunitas, respons insiden |

## 8. Checklist Rilis (wajib ✅ semua sebelum GA)

- [ ] Watermark fail-closed teruji (unit test + adversarial resample/MP3)
- [ ] Consent tier di semua jalur export (CLI, server, SDK)
- [ ] UU PDP mapping terdokumentasi (tabel §4)
- [ ] `verify` CLI watermark detector dirilis
- [ ] security.txt + kebijakan disclosure
- [ ] Model card draft (§5) dipublikasikan
- [ ] Threat P0 (T1–T3 RFC.md) status → "mitigated" dengan test bukti
- [ ] DATA_CAPS.md ada & CI provenance check hijau

---

*Dokumen produk kerja `@security` + `@localization-i18n-pro`; matriks threat penuh di RFC.md §6.*
