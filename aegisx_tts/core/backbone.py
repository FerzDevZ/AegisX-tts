"""Backbone Transformer kausal + KV-cache — docs/02 §2.2.

Spesifikasi: RMSNorm, SwiGLU, RoPE, pre-norm residual, batch=1 streaming.
Layout cache per layer: K/V dengan dim posisi di index 1 → [B, L, H, d_head]
(konsisten dengan kontrak SpeakerProfile docs/02 §2.3). `step()` memberi
paritas numerik dengan full forward — invarian streaming docs/02 §5.
"""

from __future__ import annotations

import math
from typing import Final

import torch
import torch.nn as nn
import torch.nn.functional as F

_NEG_INF: Final[float] = -1e9


class RMSNorm(nn.Module):
    """Root-mean-square norm (docs/02 §2.2: norm: rmsnorm)."""

    def __init__(self, d_model: int, eps: float = 1e-6) -> None:
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(d_model))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        variance = x.pow(2).mean(dim=-1, keepdim=True)
        normed: torch.Tensor = x * torch.rsqrt(variance + self.eps)
        return normed * self.weight


class SwiGLU(nn.Module):
    """Feed-forward SwiGLU (docs/02 §2.2: activation: swiglu)."""

    def __init__(self, d_model: int, d_ff: int) -> None:
        super().__init__()
        self.w_gate = nn.Linear(d_model, d_ff, bias=False)
        self.w_up = nn.Linear(d_model, d_ff, bias=False)
        self.w_down = nn.Linear(d_ff, d_model, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        gated: torch.Tensor = self.w_gate.forward(x)
        up: torch.Tensor = self.w_up.forward(x)
        return self.w_down.forward(F.silu(gated) * up)


class RotaryPositionalEmbedding(nn.Module):
    """RoPE klasik (Su et al.) — diterapkan pada separuh paritas d_head."""

    cos: torch.Tensor
    sin: torch.Tensor

    def __init__(self, d_head: int, max_positions: int, theta: float = 10_000.0) -> None:
        super().__init__()
        inv_freq = theta ** (-torch.arange(0, d_head, 2).float() / d_head)
        t = torch.arange(max_positions).float()
        freqs = torch.outer(t, inv_freq)  # [L, d_head//2]
        self.register_buffer("cos", freqs.cos(), persistent=False)
        self.register_buffer("sin", freqs.sin(), persistent=False)

    @staticmethod
    def _rotate_half(x: torch.Tensor) -> torch.Tensor:
        # x: [..., d_head]; pasangan (x0,x1),(x2,x3),... untuk d_head genap.
        x1 = x[..., 0::2]
        x2 = x[..., 1::2]
        out = torch.stack((-x2, x1), dim=-1)
        return out.flatten(start_dim=-2)

    def forward(self, x: torch.Tensor, start_pos: int = 0) -> torch.Tensor:
        """x: [B, L, H, d_head]; start_pos untuk mode step (cache)."""
        seq_len = x.shape[1]
        cos = self.cos[start_pos : start_pos + seq_len]  # [L, d_head//2]
        sin = self.sin[start_pos : start_pos + seq_len]
        cos = torch.repeat_interleave(cos, 2, dim=-1)  # [L, d_head]
        sin = torch.repeat_interleave(sin, 2, dim=-1)
        cos = cos[None, :, None, :]
        sin = sin[None, :, None, :]
        return x * cos + self._rotate_half(x) * sin


class CausalSelfAttention(nn.Module):
    """Attention kausal dengan KV-cache inkremental."""

    def __init__(self, d_model: int, heads: int) -> None:
        super().__init__()
        self.heads = heads
        self.d_head = d_model // heads
        self.q_proj = nn.Linear(d_model, d_model, bias=False)
        self.k_proj = nn.Linear(d_model, d_model, bias=False)
        self.v_proj = nn.Linear(d_model, d_model, bias=False)
        self.out_proj = nn.Linear(d_model, d_model, bias=False)

    def _shape(self, x: torch.Tensor) -> torch.Tensor:
        b, t, _ = x.shape
        return x.view(b, t, self.heads, self.d_head)

    def forward(
        self,
        x: torch.Tensor,
        *,
        rope: RotaryPositionalEmbedding,
        cache: list[tuple[torch.Tensor, torch.Tensor]] | None = None,
        layer_idx: int | None = None,
        start_pos: int = 0,
    ) -> torch.Tensor:
        q = self._shape(self.q_proj.forward(x))
        k = self._shape(self.k_proj.forward(x))
        v = self._shape(self.v_proj.forward(x))

        q = rope(q, start_pos)
        k = rope(k, start_pos)

        if cache is not None and layer_idx is not None:
            prev_k, prev_v = cache[layer_idx]
            k = torch.cat([prev_k, k], dim=1) if prev_k.shape[1] else k
            v = torch.cat([prev_v, v], dim=1) if prev_v.shape[1] else v
            cache[layer_idx] = (k, v)

        total_len = k.shape[1]
        q_t = q.transpose(1, 2)  # [B, H, T, d_head]
        k_t = k.transpose(1, 2)
        v_t = v.transpose(1, 2)
        scores = (q_t @ k_t.transpose(-2, -1)) / math.sqrt(self.d_head)

        # Mask kausal terhadap total panjang (cache + langkah kini).
        t = q.shape[1]
        query_pos = torch.arange(start_pos, start_pos + t, device=x.device)
        key_pos = torch.arange(total_len, device=x.device)
        mask = key_pos[None, :] > query_pos[:, None]
        scores = scores.masked_fill(mask[None, None, :, :], _NEG_INF)

        attn = F.softmax(scores, dim=-1)
        attended: torch.Tensor = attn @ v_t
        merged = attended.transpose(1, 2).contiguous().view(
            attended.shape[0], t, self.heads * self.d_head
        )
        return self.out_proj.forward(merged)


class TransformerBlock(nn.Module):
    def __init__(self, d_model: int, heads: int, d_ff: int) -> None:
        super().__init__()
        self.attn_norm = RMSNorm(d_model)
        self.attn = CausalSelfAttention(d_model, heads)
        self.ffn_norm = RMSNorm(d_model)
        self.ffn = SwiGLU(d_model, d_ff)

    def forward(
        self,
        x: torch.Tensor,
        *,
        rope: RotaryPositionalEmbedding,
        cache: list[tuple[torch.Tensor, torch.Tensor]] | None = None,
        layer_idx: int | None = None,
        start_pos: int = 0,
    ) -> torch.Tensor:
        attn_in: torch.Tensor = self.attn_norm.forward(x)
        attn_out: torch.Tensor = self.attn.forward(
            attn_in, rope=rope, cache=cache, layer_idx=layer_idx, start_pos=start_pos
        )
        x = x + attn_out
        ffn_in: torch.Tensor = self.ffn_norm.forward(x)
        x = x + self.ffn.forward(ffn_in)
        return x


class Backbone(nn.Module):
    """Transformer kausal utuh: token → representasi tersembunyi per posisi."""

    def __init__(
        self,
        vocab_size: int,
        layers: int,
        d_model: int,
        heads: int,
        d_ff: int,
        max_positions: int,
        rope_theta: float = 10_000.0,
    ) -> None:
        super().__init__()
        if layers < 1:
            raise ValueError(f"layers minimal 1, dapat {layers}")
        if d_model % heads != 0:
            raise ValueError(f"heads={heads} harus membagi habis d_model={d_model}")
        self.d_model = d_model
        self.heads = heads
        self.max_positions = max_positions
        self.token_embed = nn.Embedding(vocab_size, d_model)
        self.rope = RotaryPositionalEmbedding(d_model // heads, max_positions, rope_theta)
        self.blocks = nn.ModuleList(
            TransformerBlock(d_model, heads, d_ff) for _ in range(layers)
        )
        self.final_norm = RMSNorm(d_model)

    def new_cache(self, batch_size: int) -> list[tuple[torch.Tensor, torch.Tensor]]:
        """Cache kosong: per layer, tuple (K, V) dengan dim posisi di index 1."""
        return [
            (
                torch.zeros(batch_size, 0, self.heads, self.d_model // self.heads),
                torch.zeros(batch_size, 0, self.heads, self.d_model // self.heads),
            )
            for _ in range(len(self.blocks))
        ]

    def _check_positions(self, seq_len: int, start_pos: int) -> None:
        if start_pos + seq_len > self.max_positions:
            raise ValueError(
                f"Panjang total {start_pos + seq_len} melebihi max_positions={self.max_positions}"
            )

    def forward(self, tokens: torch.Tensor) -> torch.Tensor:
        """Full forward: [B, T] → [B, T, d_model] (paritas dengan step())."""
        self._check_positions(tokens.shape[1], 0)
        x: torch.Tensor = self.token_embed.forward(tokens)
        for block in self.blocks:
            x = block.forward(x, rope=self.rope, start_pos=0)
        return self.final_norm.forward(x)

    def step(
        self,
        token: torch.Tensor,
        cache: list[tuple[torch.Tensor, torch.Tensor]],
    ) -> tuple[torch.Tensor, list[tuple[torch.Tensor, torch.Tensor]]]:
        """Decode inkremental: 1 token → 1 vektor keluaran; cache bertambah.

        token: [B, 1]. Mengembalikan (out [B, 1, d_model], cache baru).
        """
        if token.shape[1] != 1:
            raise ValueError(
                f"step() menerima tepat 1 token per pemanggilan, dapat {token.shape[1]}"
            )
        start_pos = cache[0][0].shape[1]
        self._check_positions(1, start_pos)
        x: torch.Tensor = self.token_embed.forward(token)
        for idx, block in enumerate(self.blocks):
            x = block.forward(x, rope=self.rope, cache=cache, layer_idx=idx, start_pos=start_pos)
        return self.final_norm.forward(x), cache
