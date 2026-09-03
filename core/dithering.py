'''
File:   dithering.py
Brief:  Grayscale tone adjustment and 1-bit dithering for 203 DPI labels.
Author: Mistress-Lukutar
Date:   2026-09-03
Version: v0.1.0

Converts a grayscale image into the black/white bitmap the thermal
head prints. Three families, chosen for label content:

- Floyd-Steinberg error diffusion — photographs and gradients;
- Ordered Bayer dithering (2x2/4x4/8x8) — crisp lines, no smearing;
- Plain threshold — already black/white artwork.

Tone controls (brightness / contrast / gamma / invert) run before the
dither so a washed-out generation can still print punchy.
'''

from __future__ import annotations

import numpy as np

#: Floyd-Steinberg error diffusion.
DITHER_FLOYD_STEINBERG = "floyd-steinberg"
#: Ordered dithering with a 2x2 Bayer matrix.
DITHER_ORDERED_2 = "ordered 2x2"
#: Ordered dithering with a 4x4 Bayer matrix.
DITHER_ORDERED_4 = "ordered 4x4"
#: Ordered dithering with an 8x8 Bayer matrix.
DITHER_ORDERED_8 = "ordered 8x8"
#: Fixed threshold at 50%% gray.
DITHER_THRESHOLD = "threshold"
#: Selectable dithering methods.
DITHER_METHODS: tuple[str, ...] = (
    DITHER_FLOYD_STEINBERG,
    DITHER_ORDERED_2,
    DITHER_ORDERED_4,
    DITHER_ORDERED_8,
    DITHER_THRESHOLD,
)

#: Default threshold (mid gray) for :data:`DITHER_THRESHOLD`.
THRESHOLD = 128.0


def adjust_tone(
    gray: np.ndarray,
    brightness: float = 0.0,
    contrast: float = 0.0,
    gamma: float = 1.0,
    invert: bool = False,
) -> np.ndarray:
    '''Apply tone controls to a grayscale image.

    Args:
        gray: Float array, roughly in [0, 255].
        brightness: Added to every pixel (in gray levels, -255..255).
        contrast: -1..1; 0 keeps the image, positive values push pixels
            away from mid gray, negative values flatten them.
        gamma: >1 brightens (like gamma correction), <1 darkens.
        invert: Swap black and white.

    Returns:
        Clipped float32 array in [0, 255].
    '''
    out = gray.astype(np.float32) + brightness
    if contrast != 0.0:
        out = (out - 128.0) * (1.0 + contrast) + 128.0
    if gamma != 1.0:
        # Work in [0,1] so the power stays well-defined at 0.
        out = np.clip(out, 0.0, 255.0) / 255.0
        out = np.power(out, 1.0 / gamma) * 255.0
    if invert:
        out = 255.0 - out
    return np.clip(out, 0.0, 255.0).astype(np.float32)


def _bayer_matrix(size: int) -> np.ndarray:
    '''Recursive Bayer threshold matrix, normalized to [0, 1).

    Args:
        size: 2, 4 or 8 — must be a power of two.

    Returns:
        Float matrix (size, size).
    '''
    matrix = np.array([[0.0]], dtype=np.float32)
    while matrix.shape[0] < size:
        step = matrix.shape[0] * matrix.shape[0]
        matrix = np.block(
            [
                [matrix + 0.0 * step, matrix + 2.0 * step],
                [matrix + 3.0 * step, matrix + 1.0 * step],
            ]
        )
    cells = size * size
    # Cell c fires at gray < (c + 0.5) / cells, giving an even response.
    return (matrix + 0.5) / cells


def _dither_ordered(
    gray: np.ndarray, size: int
) -> np.ndarray:
    '''Ordered (Bayer) dithering, tile-vectorized.

    Args:
        gray: Float array in [0, 255].
        size: Bayer matrix size (2, 4 or 8).

    Returns:
        Bool array; True where an ink dot is placed.
    '''
    matrix = _bayer_matrix(size) * 255.0
    h, w = gray.shape
    tiles_h = (h + size - 1) // size
    tiles_w = (w + size - 1) // size
    padded = np.full((tiles_h * size, tiles_w * size), 255.0, np.float32)
    padded[:h, :w] = gray
    blocks = padded.reshape(
        tiles_h, size, tiles_w, size
    ).swapaxes(1, 2)
    dots = blocks < matrix[np.newaxis, np.newaxis, :, :]
    out = dots.reshape(tiles_h * size, tiles_w * size)[:h, :w]
    return np.ascontiguousarray(out)


def _dither_floyd_steinberg(gray: np.ndarray) -> np.ndarray:
    '''Floyd-Steinberg error diffusion via PIL's C implementation.

    Same engine the proven standalone test script used (``convert("1",
    dither=FLOYDSTEINBERG)``) — exact serial diffusion at C speed.

    Args:
        gray: Float array in [0, 255].

    Returns:
        Bool array; True means an ink dot is placed.
    '''
    from PIL import Image

    pil_gray = Image.fromarray(
        np.clip(gray, 0.0, 255.0).astype(np.uint8), mode="L"
    )
    pil_bits = pil_gray.convert(
        "1", dither=Image.Dither.FLOYDSTEINBERG
    )
    # PIL "1" is True=white; our convention is True=ink (black).
    return np.logical_not(np.asarray(pil_bits))


def dither(gray: np.ndarray, method: str = DITHER_FLOYD_STEINBERG) -> np.ndarray:
    '''Reduce a grayscale image to the 1-bit print bitmap.

    Args:
        gray: Float array in [0, 255]; 0 is black.
        method: One of :data:`DITHER_METHODS`.

    Returns:
        Bool array of the same shape; True means an ink (black) dot.

    Raises:
        ValueError: On an unknown method.
    '''
    if method == DITHER_FLOYD_STEINBERG:
        return _dither_floyd_steinberg(gray)
    if method == DITHER_ORDERED_2:
        return _dither_ordered(gray, 2)
    if method == DITHER_ORDERED_4:
        return _dither_ordered(gray, 4)
    if method == DITHER_ORDERED_8:
        return _dither_ordered(gray, 8)
    if method == DITHER_THRESHOLD:
        return gray < THRESHOLD
    raise ValueError(f"unknown dithering method: {method!r}")
