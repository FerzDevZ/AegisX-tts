"""Unit test Codec RVQ decoder (docs/02 §4).

Properti yang dijamin:
1. Frame boundary: T frame token → T × 1920 sampel (24 kHz × 80 ms) — tepat.
2. Rentang output float32 [-1, 1] (kontrak docs/02 §4 PCM).
3. Paritas streaming: decode(all frames) == concat(decode per frame)
   (frame RVQ independen — invarian streaming docs/02 §5.2).
4. Determinisme: bobot sama → output bit-identik.
5. Validasi: token di luar codebook → error; jumlah level salah → error.
"""

from __future__ import annotations

import pytest
import torch

from aegisx_tts.constants import SAMPLES_PER_FRAME
from aegisx_tts.core.codec import RvqDecoder

CODEBOOK = 1024
LEVELS = 8


def _make_decoder(seed: int = 20260906) -> RvqDecoder:
    torch.manual_seed(seed)
    return RvqDecoder(codebook_size=CODEBOOK, rvq_levels=LEVELS)


def _random_tokens(frames: int, seed: int = 1) -> torch.Tensor:
    g = torch.Generator().manual_seed(seed)
    return torch.randint(0, CODEBOOK, (1, LEVELS, frames), generator=g)


class TestFrameBoundary:
    def test_satu_frame_tepat_1920_sampel(self) -> None:
        dec = _make_decoder()
        out = dec.decode(_random_tokens(1))
        assert out.shape == (1, SAMPLES_PER_FRAME)
        assert SAMPLES_PER_FRAME == 1920

    def test_multi_frame_kelipatan_tepat(self) -> None:
        dec = _make_decoder()
        for frames in (2, 5, 17):
            out = dec.decode(_random_tokens(frames))
            assert out.shape == (1, frames * SAMPLES_PER_FRAME)


class TestOutputContract:
    def test_rentang_dan_dtype(self) -> None:
        dec = _make_decoder()
        out = dec.decode(_random_tokens(3))
        assert out.dtype == torch.float32
        assert out.min() >= -1.0 and out.max() <= 1.0

    def test_determinisme(self) -> None:
        dec = _make_decoder()
        tokens = _random_tokens(4)
        assert torch.equal(dec.decode(tokens), dec.decode(tokens))


class TestStreamingParity:
    def test_decode_per_frame_identik_decode_batch(self) -> None:
        dec = _make_decoder()
        dec.eval()
        tokens = _random_tokens(6)
        with torch.no_grad():
            full = dec.decode(tokens)
            chunks = [
                dec.decode(tokens[:, :, i : i + 1]) for i in range(tokens.shape[2])
            ]
        streamed = torch.cat(chunks, dim=1)
        assert torch.allclose(full, streamed, atol=1e-5, rtol=1e-5)


class TestValidation:
    def test_token_di_luar_codebook_ditolak(self) -> None:
        dec = _make_decoder()
        bad = _random_tokens(1)
        bad[0, 0, 0] = CODEBOOK  # index maksimum sah = CODEBOOK-1
        with pytest.raises(ValueError, match="codebook"):
            dec.decode(bad)

    def test_jumlah_level_salah_ditolak(self) -> None:
        dec = _make_decoder()
        wrong = torch.randint(0, CODEBOOK, (1, LEVELS + 1, 2))
        with pytest.raises(ValueError, match="level"):
            dec.decode(wrong)

    def test_batch_kosong_ditolak(self) -> None:
        dec = _make_decoder()
        with pytest.raises(ValueError, match="frame"):
            dec.decode(torch.randint(0, CODEBOOK, (1, LEVELS, 0)))
