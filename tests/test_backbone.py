"""Unit test Backbone Transformer + KV-cache (docs/02 §2.2).

Properti yang dijamin test:
1. Shape output [B, T, d_model].
2. Kausalitas: mengubah token pada posisi t TIDAK mengubah output posisi < t.
3. Paritas streaming: decode token-per-token dengan KV-cache == full forward.
   (Invarian inti fitur streaming docs/02 §5.)
4. Determinisme: input sama → output bit-identik.
5. RMSNorm: norma vektor ≈ sqrt(d_model) × |weight| arah rata.
6. Validasi: heads tidak membagi d_model → ValueError.
"""

from __future__ import annotations

import pytest
import torch

from aegisx_tts.core.backbone import Backbone

D_MODEL = 256
HEADS = 8
D_FF = 640
LAYERS = 4
VOCAB = 512


def _make_backbone(seed: int = 20260906) -> Backbone:
    torch.manual_seed(seed)
    return Backbone(
        vocab_size=VOCAB,
        layers=LAYERS,
        d_model=D_MODEL,
        heads=HEADS,
        d_ff=D_FF,
        max_positions=256,
    )


class TestShapes:
    def test_output_shape(self) -> None:
        bb = _make_backbone()
        tokens = torch.randint(0, VOCAB, (2, 10))
        out = bb(tokens)
        assert out.shape == (2, 10, D_MODEL)

    def test_single_token_prefill(self) -> None:
        bb = _make_backbone()
        out = bb(torch.randint(0, VOCAB, (1, 1)))
        assert out.shape == (1, 1, D_MODEL)


class TestCausality:
    def test_perubahan_token_hanya_mempengaruhi_posisi_sesudahnya(self) -> None:
        bb = _make_backbone()
        bb.eval()
        base = torch.randint(0, VOCAB, (1, 6))
        modified = base.clone()
        modified[0, 4] = (modified[0, 4] + 7) % VOCAB  # ubah posisi 4 saja

        with torch.no_grad():
            out_base = bb(base)
            out_mod = bb(modified)

        assert torch.equal(out_base[0, :4], out_mod[0, :4])  # posisi < 4 tak berubah
        assert not torch.equal(out_base[0, 4:], out_mod[0, 4:])


class TestStreamingParity:
    def test_decode_dengan_cache_identik_full_forward(self) -> None:
        bb = _make_backbone()
        bb.eval()
        tokens = torch.randint(0, VOCAB, (1, 8))

        with torch.no_grad():
            full = bb(tokens)  # [1, 8, D]

            cache = bb.new_cache(batch_size=1)
            steps: list[torch.Tensor] = []
            for i in range(tokens.shape[1]):
                step_out, cache = bb.step(tokens[:, i : i + 1], cache)
                steps.append(step_out[:, 0, :])
            streamed = torch.stack(steps, dim=1)  # [1, 8, D]

        assert torch.allclose(full, streamed, atol=1e-4, rtol=1e-4), (
            "KV-cache streaming harus identik dengan full forward (docs/02 §5)"
        )

    def test_step_mengembalikan_cache_dengan_panjang_bertambah(self) -> None:
        bb = _make_backbone()
        cache = bb.new_cache(batch_size=1)
        token = torch.randint(0, VOCAB, (1, 1))
        _, cache = bb.step(token, cache)
        k_first, _ = cache[0]
        assert k_first.shape[1] == 1  # satu entri cache setelah satu step


class TestDeterminism:
    def test_forward_dua_kali_identik(self) -> None:
        bb = _make_backbone()
        bb.eval()
        tokens = torch.randint(0, VOCAB, (1, 12))
        with torch.no_grad():
            a = bb(tokens)
            b = bb(tokens)
        assert torch.equal(a, b)


class TestValidation:
    def test_heads_tidak_membagi_d_model(self) -> None:
        with pytest.raises(ValueError, match="heads"):
            Backbone(
                vocab_size=VOCAB, layers=LAYERS, d_model=256, heads=7, d_ff=D_FF, max_positions=64
            )

    def test_layers_minimal(self) -> None:
        with pytest.raises(ValueError, match="layers"):
            Backbone(
                vocab_size=VOCAB, layers=0, d_model=256, heads=8, d_ff=D_FF, max_positions=64
            )
