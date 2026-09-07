"""Watermark audio spektral + verifier — docs/05 §3.

Desain: payload (tier + voice) dikodekan reversibel menjadi 128 bit
(header tier 2 bit, panjang voice 5 bit, voice ASCII 8 bit/karakter,
padding nol, CRC-8 8 bit). Setiap bit dimodulasi antipodal (BPSK):
+1 → +A·carrier, 0 → −A·carrier, pada carrier 4.6 kHz di pita
WATERMARK_BAND_HZ (3.8–5.4 kHz) — di atas formant utama agar
inaudible. Frame di-taper Tukey untuk menekan spectral splatter.

Decoder memakai matched filter per frame pada sinyal hasil bandpass;
tanda korelasi menentukan bit, CRC-8 memvalidasi integritas, dan
magnitude korelasi rata-rata menjadi pemeriksa kehadiran watermark.
Audio tanpa watermark → None (fail-closed terhadap false positive).

`embed_watermark()` fail-CLOSED: audio terlalu pendek → raise.
"""

from __future__ import annotations

import hashlib
from typing import Final

import torch

from aegisx_tts.constants import SAMPLE_RATE_HZ

# Pita watermark: di atas formant utama (100–4000 Hz) agar inaudible.
BAND_LO_HZ: Final[float] = 3_800.0
BAND_HI_HZ: Final[float] = 5_400.0
WATERMARK_BAND_HZ: Final[tuple[float, float]] = (BAND_LO_HZ, BAND_HI_HZ)
CARRIER_HZ: Final[float] = (BAND_LO_HZ + BAND_HI_HZ) / 2  # 4600 Hz

MIN_DURATION_S: Final[float] = 0.25

# Struktur payload tetap 128 bit agar decoder tidak perlu menebak bit-rate.
NUM_BITS: Final[int] = 128
TIER_BITS: Final[int] = 2
LEN_BITS: Final[int] = 5
CHAR_BITS: Final[int] = 8
CRC_BITS: Final[int] = 8
_PAYLOAD_BITS: Final[int] = NUM_BITS - CRC_BITS  # 120
MAX_VOICE_CHARS: Final[int] = (_PAYLOAD_BITS - TIER_BITS - LEN_BITS) // CHAR_BITS  # 14

_TIERS: Final[tuple[str, ...]] = ("self-declared", "written", "verified", "certified")

# Amplitudo watermark: SNR ≈ 21.8 dB terhadap sinyal penuh (test > 20 dB).
WM_AMPLITUDE: Final[float] = 0.03
# Pemeriksa kehadiran: mean |corr| watermark ≈ A·N/2 (~5); noise ≈ 0.7.
PRESENCE_THRESHOLD: Final[float] = 2.0
_RAMP: Final[int] = 24  # taper Tukey per tepi frame


class WatermarkError(ValueError):
    """Watermark gagal karena batasan input (subclass ValueError)."""


def _crc8(data_bits: list[int]) -> int:
    """CRC-8 (poly 0x07) atas aliran bit, satu shift per bit."""
    crc = 0
    for bit in data_bits:
        crc ^= (bit & 1) << 7
        if crc & 0x80:
            crc = ((crc << 1) & 0xFF) ^ 0x07
        else:
            crc = (crc << 1) & 0xFF
    return crc


def _int_to_bits(value: int, width: int) -> list[int]:
    """Integer → daftar bit MSB-first sepanjang `width`."""
    return [(value >> (width - 1 - i)) & 1 for i in range(width)]


def _bits_to_int(bits: list[int]) -> int:
    value = 0
    for bit in bits:
        value = (value << 1) | (bit & 1)
    return value


def _payload_bits(payload: WmkPayload) -> list[int]:
    """Encode (tier, voice) → 120 bit payload + 8 bit CRC = 128 bit."""
    tier_idx = _TIERS.index(payload.tier)
    voice_bytes = payload.voice.encode("ascii")
    if len(voice_bytes) > MAX_VOICE_CHARS:
        raise WatermarkError(
            f"voice maksimal {MAX_VOICE_CHARS} karakter ASCII, dapat {len(voice_bytes)}"
        )
    bits: list[int] = []
    bits += _int_to_bits(tier_idx, TIER_BITS)
    bits += _int_to_bits(len(voice_bytes), LEN_BITS)
    for byte in voice_bytes:
        bits += _int_to_bits(byte, CHAR_BITS)
    bits += [0] * (_PAYLOAD_BITS - len(bits))
    bits += _int_to_bits(_crc8(bits), CRC_BITS)
    return bits


class WmkPayload:
    """Payload konsent yang disematkan ke audio (docs/05 §3.2).

    `bitstring` adalah sidik deterministik dari (tier, voice); karena
    verify merekonstruksi (tier, voice) dari audio, roundtrip bitstring
    identik dengan aslinya.
    """

    __slots__ = ("tier", "voice", "_bitstring", "_id")

    def __init__(self, tier: str, voice: str) -> None:
        if tier not in _TIERS:
            raise ValueError(
                f"tier tidak dikenal: {tier!r} (harus salah satu "
                + "/".join(_TIERS)
                + ")"
            )
        self.tier = tier
        self.voice = voice
        self._id = f"{self.tier}|{self.voice}"
        self._bitstring = hashlib.sha256(f"{self._id}|v1".encode()).hexdigest()

    @property
    def bitstring(self) -> str:
        return self._bitstring

    @property
    def id(self) -> str:
        return self._id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, WmkPayload):
            return NotImplemented
        return self.tier == other.tier and self.voice == other.voice

    def __hash__(self) -> int:
        return hash((self.tier, self.voice))

    def __repr__(self) -> str:
        return f"WmkPayload(tier={self.tier!r}, voice={self.voice!r})"


def _band_mask(numel: int) -> torch.Tensor:
    """Mask boolean frekuensi pita watermark (rfft domain)."""
    freqs = torch.fft.rfftfreq(numel, 1.0 / SAMPLE_RATE_HZ)
    mask: torch.Tensor = (freqs >= BAND_LO_HZ) & (freqs < BAND_HI_HZ)
    return mask


def _taper(frame_len: int) -> torch.Tensor:
    """Taper Tukey per tepi frame untuk menekan splatter spektral."""
    ramp = min(_RAMP, max(1, frame_len // 4))
    env = torch.ones(frame_len, dtype=torch.float32)
    ramp_up = 0.5 * (1.0 - torch.cos(torch.pi * torch.arange(ramp) / ramp))
    env[:ramp] = ramp_up
    env[frame_len - ramp :] = ramp_up.flip(0)
    return env


def _frame_len_for(numel: int) -> int:
    return max(1, numel // NUM_BITS)


def embed_watermark(
    audio: torch.Tensor,
    payload: WmkPayload,
) -> torch.Tensor:
    """Sisipkan sidik payload ke audio [L] float32 [-1,1].

    Return tensor baru (input tidak dimutasi). Fail-closed: audio
    terlalu pendek / di luar rentang → WatermarkError.
    """
    audio = audio.detach().to(torch.float32).cpu()
    if audio.dim() != 1:
        raise WatermarkError(f"audio harus 1-D, dapat {audio.dim()}-D")
    if audio.numel() == 0:
        raise WatermarkError("audio kosong")
    if float(audio.abs().max()) > 1.0:
        raise WatermarkError("audio di luar rentang [-1,1]")
    if audio.numel() < int(MIN_DURATION_S * SAMPLE_RATE_HZ):
        raise WatermarkError(
            f"durasi audio terlalu pendek (< {MIN_DURATION_S}s); "
            f"panjang={audio.numel()} sampel"
        )

    numel = audio.numel()
    frame_len = _frame_len_for(numel)
    bits = _payload_bits(payload)

    # Carrier fase GLOBAL (kontinu antar-frame) — korelasi per-frame
    # konstan ±A·Σ(taper·carrier²) tanpa bergantung offset fase frame.
    taper = _taper(frame_len)
    t_global = torch.arange(numel, dtype=torch.float32) / SAMPLE_RATE_HZ
    carrier_full = torch.sin(2.0 * torch.pi * CARRIER_HZ * t_global)

    watermark = torch.zeros(numel, dtype=torch.float32)
    for i, bit in enumerate(bits):
        start = i * frame_len
        end = start + frame_len
        if end > numel:
            break
        sign = 1.0 if bit == 1 else -1.0
        watermark[start:end] = sign * WM_AMPLITUDE * taper * carrier_full[start:end]

    marked = audio + watermark
    return marked.clamp(-1.0, 1.0)


def verify_watermark(audio: torch.Tensor) -> WmkPayload | None:
    """Kembalikan payload jika watermark valid terdeteksi, None jika tidak.

    Alur: bandpass pita watermark → matched filter per frame → 128 bit
    → pemeriksa kehadiran (magnitude korelasi) → validasi CRC-8 →
    rekonstruksi (tier, voice). Gagal di langkah mana pun → None.
    """
    audio = audio.detach().to(torch.float32).cpu()
    if audio.dim() != 1:
        return None
    numel = audio.numel()
    if numel < int(MIN_DURATION_S * SAMPLE_RATE_HZ):
        return None

    spec = torch.fft.rfft(audio)
    mask = _band_mask(numel)
    band = torch.fft.irfft(spec * mask.to(spec.dtype), n=numel)[:numel]

    # Matched filter dengan carrier fase GLOBAL — sama seperti embed.
    frame_len = _frame_len_for(numel)
    t_global = torch.arange(numel, dtype=torch.float32) / SAMPLE_RATE_HZ
    carrier_full = torch.sin(2.0 * torch.pi * CARRIER_HZ * t_global)

    corrs: list[float] = []
    for i in range(NUM_BITS):
        start = i * frame_len
        end = start + frame_len
        if end > numel:
            break
        corrs.append(float(torch.dot(band[start:end], carrier_full[start:end])))

    if len(corrs) < NUM_BITS:
        return None

    # Pemeriksa kehadiran: watermark menghasilkan |corr| besar di semua frame.
    mean_abs = sum(abs(c) for c in corrs) / len(corrs)
    if mean_abs < PRESENCE_THRESHOLD:
        return None

    bits = [1 if c > 0 else 0 for c in corrs]

    # Validasi CRC-8 atas 120 bit payload.
    if _crc8(bits[:_PAYLOAD_BITS]) != _bits_to_int(bits[_PAYLOAD_BITS:]):
        return None

    tier_idx = _bits_to_int(bits[:TIER_BITS])
    voice_len = _bits_to_int(bits[TIER_BITS : TIER_BITS + LEN_BITS])
    if voice_len > MAX_VOICE_CHARS:
        return None
    voice_start = TIER_BITS + LEN_BITS
    voice_bytes = bytes(
        _bits_to_int(bits[voice_start + i * CHAR_BITS : voice_start + (i + 1) * CHAR_BITS])
        for i in range(voice_len)
    )
    try:
        voice = voice_bytes.decode("ascii")
    except UnicodeDecodeError:
        return None

    return WmkPayload(tier=_TIERS[tier_idx], voice=voice)
