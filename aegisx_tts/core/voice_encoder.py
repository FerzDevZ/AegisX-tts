"""VoiceEncoder: audio referensi → SpeakerProfile (docs/02 §2.3).

Jalur voice cloning: waveform [1, N] @ 24 kHz → prefix KV-cache per layer
[n_layers, 2, prefix_len, heads*d_head]. V1 memakai CNN mel-mvp + self-attention
deterministik; bobot pretrained M2 menggantikan parameter tanpa mengubah
kontrak. Semua validasi AC-7 (durasi, sample rate, silence) aktif sejak kini.
"""

from __future__ import annotations

import torch
import torch.nn as nn

from aegisx_tts.constants import (
    MAX_REF_AUDIO_SECONDS,
    MIN_REF_AUDIO_SECONDS,
    SAMPLE_RATE_HZ,
)
from aegisx_tts.core.speaker import SpeakerProfile, SpeakerSource


class _MelFrontend(nn.Module):
    """Frontend sederhana: conv stack menurunkan 24 kHz → frame 20 ms."""

    def __init__(self, d_model: int) -> None:
        super().__init__()
        self.stack = nn.Sequential(
            nn.Conv1d(1, d_model // 4, kernel_size=480, stride=160, padding=160),
            nn.GELU(),
            nn.Conv1d(d_model // 4, d_model // 2, kernel_size=5, padding=2),
            nn.GELU(),
            nn.Conv1d(d_model // 2, d_model, kernel_size=5, padding=2),
            nn.GELU(),
        )

    def forward(self, wave: torch.Tensor) -> torch.Tensor:
        # wave: [1, N] mono → Conv1d butuh [B=1, C=1, L=N].
        if wave.dim() == 2:
            wave = wave.unsqueeze(1)
        out: torch.Tensor = self.stack(wave)
        return out


class VoiceEncoder(nn.Module):
    """Waveform referensi → prefix KV-cache yang siap digabung ke backbone."""

    def __init__(self, n_layers: int, prefix_len: int, heads: int, d_head: int) -> None:
        super().__init__()
        if heads < 1 or d_head < 1 or n_layers < 1 or prefix_len < 1:
            raise ValueError("n_layers, prefix_len, heads, d_head harus >= 1")
        self.n_layers = n_layers
        self.prefix_len = prefix_len
        self.heads = heads
        self.d_head = d_head
        d_model = heads * d_head
        self.frontend = _MelFrontend(d_model)
        self.gru = nn.GRU(d_model, d_model, batch_first=True)
        self.to_k = nn.Linear(d_model, d_model)
        self.to_v = nn.Linear(d_model, d_model)
        self.layer_norm = nn.LayerNorm(d_model)

    def _validate(self, wave: torch.Tensor, sample_rate: int) -> None:
        if wave.dim() != 2 or wave.shape[0] != 1:
            raise ValueError(
                f"Waveform harus berdimensi [1, N] mono, dapat {tuple(wave.shape)}"
            )
        if sample_rate != SAMPLE_RATE_HZ:
            raise ValueError(
                f"sample_rate harus {SAMPLE_RATE_HZ}, dapat {sample_rate} "
                "(resample di pipeline data, docs/03 §4)"
            )
        seconds = wave.shape[1] / sample_rate
        if seconds < MIN_REF_AUDIO_SECONDS:
            raise ValueError(
                f"Sampel audio minimal {MIN_REF_AUDIO_SECONDS:.0f} detik, "
                f"terdeteksi {seconds:.1f} s"
            )
        if seconds > MAX_REF_AUDIO_SECONDS:
            raise ValueError(
                f"Sampel audio maksimal {MAX_REF_AUDIO_SECONDS:.0f} detik, "
                f"terdeteksi {seconds:.1f} s"
            )
        rms = wave.pow(2).mean().sqrt()
        if rms < 1e-4:
            raise ValueError("Audio senyap (RMS ~ 0) — tidak dapat diekstrak suaranya")

    def encode(self, wave: torch.Tensor, sample_rate: int) -> SpeakerProfile:
        """Waveform [1, N] mono @ 24 kHz → SpeakerProfile source=CLONED.

        Raises:
            ValueError: validasi AC-7 gagal (durasi, sample rate, silence).
        """
        self._validate(wave, sample_rate)
        feats: torch.Tensor = self.frontend.forward(wave)  # [1, D, T]
        seq: torch.Tensor = feats.transpose(1, 2)  # [1, T, D]

        # Pooling deterministik ke prefix_len: split rata + mean per segmen.
        t = seq.shape[1]
        if t < self.prefix_len:
            pad = seq.new_zeros(1, self.prefix_len - t, seq.shape[2])
            seq = torch.cat([seq, pad], dim=1)
            t = self.prefix_len
        seg = t // self.prefix_len
        usable = seg * self.prefix_len
        pooled = seq[:, :usable, :].reshape(1, self.prefix_len, seg, -1).mean(dim=2)

        hidden: torch.Tensor = self.layer_norm.forward(pooled)
        gru_out, _ = self.gru.forward(hidden)
        k: torch.Tensor = self.to_k.forward(gru_out).squeeze(0)  # [Lp, D]
        v: torch.Tensor = self.to_v.forward(gru_out).squeeze(0)  # [Lp, D]
        # V1: K/V bersama antar layer (repeat deterministik); bobot per-layer
        # sebenarnya hadir bersama pretrained M2 tanpa mengubah kontrak shape.
        kv_single = torch.stack([k, v], dim=0)  # [2, Lp, D]
        d_total = self.heads * self.d_head
        kv = (
            kv_single.unsqueeze(0)
            .expand(self.n_layers, 2, self.prefix_len, d_total)
            .contiguous()
        )  # [n_layers, 2, prefix_len, d_total]

        return SpeakerProfile(
            kv_cache=kv.detach(),
            sample_rate=SAMPLE_RATE_HZ,
            source=SpeakerSource.CLONED,
            watermark_enabled=True,  # fail-closed, docs/05 §3
            consent=None,
        )
