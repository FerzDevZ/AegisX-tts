"""Codec RVQ decoder — docs/02 §4.

Residual Vector Quantization decoder: token [B, levels, frames] → PCM
float32 [-1, 1] @ 24 kHz, dengan invarian frame tepat 1920 sampel (80 ms).
Decoder bersifat frame-lokal (frame i hanya dari token frame i) sehingga
streaming per-frame identik dengan decode batch — paritas diuji eksplisit.

Arsitektur per level (residual):
  s_l = UpsampleConv(Embedding_l(tokens_l))   # transposed-conv 2×
  residual dikurangi antar-level; level terakhir langsung jadi sinyal.
Implementasi v0.1: residual model sebagai selisih kontribusi level l−1 vs l
(deterministik, tanpa bobot pretrained) — kontrak tensor & boundary frame
sudah final sehingga bobot M2 tinggal mengganti parameter, bukan antarmuka.
"""

from __future__ import annotations

import torch
import torch.nn as nn
from torch.nn.utils.parametrizations import weight_norm


class RvqDecoder(nn.Module):
    """Decoder RVQ frame-lokal yang streaming-safe.

    Kontrak:
        - Input: LongTensor [B, rvq_levels, frames], nilai < codebook_size.
        - Output: float32 [B, frames * SAMPLES_PER_FRAME], rentang [-1, 1].
    """

    def __init__(
        self,
        codebook_size: int,
        rvq_levels: int,
        d_model: int = 256,
        upsample_factor: int = 1920,
    ) -> None:
        super().__init__()
        if codebook_size < 256:
            raise ValueError(f"codebook_size minimal 256, dapat {codebook_size}")
        if rvq_levels < 1:
            raise ValueError(f"rvq_levels minimal 1, dapat {rvq_levels}")
        self.codebook_size = codebook_size
        self.rvq_levels = rvq_levels
        self.d_model = d_model

        self.embeddings = nn.ModuleList(
            nn.Embedding(codebook_size, d_model) for _ in range(rvq_levels)
        )
        # "Upsampler" frame → 1920 sampel: ConvTranspose1d dengan stride persis
        # 1920 menjamin boundary frame tanpa tumpang tindih.
        self.upsample = weight_norm(
            nn.ConvTranspose1d(d_model, 1, kernel_size=upsample_factor, stride=upsample_factor)
        )
        self.level_gain = nn.Parameter(torch.ones(rvq_levels))

    def _validate(self, tokens: torch.Tensor) -> None:
        if tokens.dim() != 3:
            raise ValueError(
                f"Token harus berdimensi 3 [B, levels, frames], dapat {tuple(tokens.shape)}"
            )
        if tokens.shape[1] != self.rvq_levels:
            raise ValueError(
                f"Jumlah level token {tokens.shape[1]} != rvq_levels decoder {self.rvq_levels}"
            )
        if tokens.shape[2] == 0:
            raise ValueError("Jumlah frame harus > 0")
        if int(tokens.max()) >= self.codebook_size or int(tokens.min()) < 0:
            raise ValueError(
                f"Token di luar rentang codebook [0, {self.codebook_size - 1}]"
            )

    def decode(self, tokens: torch.Tensor) -> torch.Tensor:
        """Token [B, levels, frames] → PCM float32 [B, frames × 1920]."""
        self._validate(tokens)
        # RVQ decode = jumlah kontribusi tiap level; semantik residual
        # (level tinggi mengoreksi level rendah) ditanamkan saat training
        # codebook di M2 — graph decoder sendiri frame-lokal murni.
        x: torch.Tensor = torch.zeros(tokens.shape[0], self.d_model, tokens.shape[2])
        for level in range(self.rvq_levels):
            emb: torch.Tensor = self.embeddings[level].forward(tokens[:, level, :])  # [B, F, D]
            x = x + emb.transpose(1, 2) * self.level_gain[level]
        audio: torch.Tensor = self.upsample.forward(x)  # [B, 1, F*1920]
        return torch.tanh(audio).squeeze(1).float()

    def forward(self, tokens: torch.Tensor) -> torch.Tensor:
        return self.decode(tokens)
