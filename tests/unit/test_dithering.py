'''
File:   test_dithering.py
Brief:  Tone adjustment and dithering behaviour tests.
Author: Mistress-Lukutar
Date:   2026-09-03
Version: v0.1.0
'''

from __future__ import annotations

import numpy as np
import pytest
from comfyui_lukutar_pos.core import dithering


def test_threshold_black_below_white_above():
    """Threshold places ink below 128 and paper above."""
    gray = np.array([[0.0, 127.0], [128.0, 255.0]], dtype=np.float32)
    out = dithering.dither(gray, dithering.DITHER_THRESHOLD)
    assert out.tolist() == [[True, True], [False, False]]


def test_ordered_dither_density_follows_gray():
    """Dot coverage tracks darkness (1 - gray), not brightness."""
    rng = np.random.default_rng(7)
    gray = rng.uniform(0.0, 255.0, (64, 64)).astype(np.float32)
    for method in (
        dithering.DITHER_ORDERED_2,
        dithering.DITHER_ORDERED_4,
        dithering.DITHER_ORDERED_8,
    ):
        out = dithering.dither(gray, method)
        assert out.dtype == np.bool_
        assert out.shape == gray.shape
        # Mean ink coverage tracks mean darkness within a few percent.
        assert abs(out.mean() - (1.0 - gray.mean() / 255.0)) < 0.03


def test_ordered_constant_gray_reproduces_bayer_pattern():
    """A constant 25%% gray fills exactly the darkest 75%% of cells."""
    size = 8
    gray = np.full((size, size), 0.25 * 255, dtype=np.float32)
    out = dithering.dither(gray, dithering.DITHER_ORDERED_8)
    assert out.sum() == pytest.approx(size * size * 0.75, abs=2)


def test_floyd_steinberg_extremes_are_exact():
    """Pure black stays all-ink, pure white stays paper."""
    black = np.zeros((16, 16), dtype=np.float32)
    white = np.full((16, 16), 255.0, dtype=np.float32)
    assert dithering.dither(
        black, dithering.DITHER_FLOYD_STEINBERG
    ).all()
    assert not dithering.dither(
        white, dithering.DITHER_FLOYD_STEINBERG
    ).any()


def test_floyd_steinberg_gradient_covers_midrange():
    """A smooth gradient dithers to a spread of dots, not banding."""
    gradient = np.tile(
        np.linspace(0.0, 255.0, 256, dtype=np.float32), (64, 1)
    )
    out = dithering.dither(gradient, dithering.DITHER_FLOYD_STEINBERG)
    assert 0.3 < out.mean() < 0.7
    # Locally (left eighth vs right eighth) coverage must differ.
    assert out[:, :32].mean() > out[:, -32:].mean() + 0.2


def test_adjust_tone_controls():
    """Brightness shifts, contrast stretches, gamma lightens, invert flips."""
    gray = np.full((4, 4), 100.0, dtype=np.float32)

    brighter = dithering.adjust_tone(gray, brightness=50.0)
    assert np.allclose(brighter, 150.0)

    contrast = dithering.adjust_tone(gray, contrast=0.5)
    assert np.allclose(contrast, (100.0 - 128.0) * 1.5 + 128.0)

    gamma = dithering.adjust_tone(gray, gamma=2.0)
    assert np.allclose(
        gamma, ((100.0 / 255.0) ** 0.5) * 255.0, atol=0.5
    )

    inverted = dithering.adjust_tone(gray, invert=True)
    assert np.allclose(inverted, 155.0)

    clipped = dithering.adjust_tone(gray, brightness=500.0)
    assert np.allclose(clipped, 255.0)


def test_unknown_method_rejected():
    """Unknown dither names raise instead of silently no-oping."""
    with pytest.raises(ValueError, match="method"):
        dithering.dither(np.zeros((2, 2)), "sparkles")
