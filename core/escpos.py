'''
File:   escpos.py
Brief:  ESC/POS byte-stream builder for the Custom TPTCM60/112 graphic page.
Author: Mistress-Lukutar
Date:   2026-09-03
Version: v0.1.0

Implements exactly the command subset used for raster label printing in
ESC/POS emulation (printer manual rev 1.35, section 3.2.2):

- ``ESC @``           initialize printer
- ``ESC x n``         speed/quality mode (0 draft, 1 normal, 2 high)
- ``ESC FD nL nH``    receive graphic page (ram bank) from the port;
                      MSByte of each 16-bit word first, one dotline is
                      G28 / H52 words, at most 16384 words per transfer
- ``ESC FA n xH xL yH yL``
                      print graphic bank (n=0: ram bank) starting at
                      dotline xL+xH*256 for yL+yH*256 lines
- ``ESC i`` / ``ESC m``
                      total / partial cut (ignored by printers without
                      a cutter)
- ``LF``              print and line feed

The G model is the TPTCM60 (60 mm paper, 448 print dots, 28 words per
dotline, 585 dotlines max); the H model is the TPTCM112 (112 mm paper,
832 dots, 52 words, 315 dotlines max). Pure byte building — no I/O here.
'''

from __future__ import annotations

import numpy as np

#: Identifier of the 60 mm printer model (TPTCM60 family).
MODEL_TPTCM60 = "TPTCM60 (60mm, 448 dots)"
#: Identifier of the 112 mm printer model (TPTCM112 family).
MODEL_TPTCM112 = "TPTCM112 (112mm, 832 dots)"
#: Selectable printer models (affects graphic page geometry only).
PRINT_MODELS: tuple[str, ...] = (MODEL_TPTCM60, MODEL_TPTCM112)

#: Draft mode — high speed.
QUALITY_DRAFT = "draft (high speed)"
#: Normal mode.
QUALITY_NORMAL = "normal"
#: High quality — low speed (may be noisy).
QUALITY_HIGH = "high quality (low speed)"
#: Selectable speed/quality modes for ``ESC x n``.
QUALITY_MODES: tuple[str, ...] = (QUALITY_DRAFT, QUALITY_NORMAL, QUALITY_HIGH)

#: No finishing command after the label.
FINISH_NONE = "none"
#: Just the trailing line feed of the label payload.
FINISH_FEED = "feed"
#: Total cut (``ESC i``); ignored when the printer has no cutter.
FINISH_TOTAL_CUT = "total cut"
#: Partial cut (``ESC m``); ignored when the printer has no cutter.
FINISH_PARTIAL_CUT = "partial cut"
#: Selectable finishing commands.
FINISH_MODES: tuple[str, ...] = (
    FINISH_NONE,
    FINISH_FEED,
    FINISH_TOTAL_CUT,
    FINISH_PARTIAL_CUT,
)

#: Print width of the G model in dots.
WIDTH_DOTS_G = 448
#: Print width of the H model in dots.
WIDTH_DOTS_H = 832
#: Graphic page height of the G model in dotlines.
PAGE_LINES_G = 585
#: Graphic page height of the H model in dotlines.
PAGE_LINES_H = 315
#: Words per graphic page dotline for the G model.
WORDS_PER_LINE_G = 28
#: Words per graphic page dotline for the H model.
WORDS_PER_LINE_H = 52
#: Hard limit of one ``ESC FD`` transfer, in 16-bit words.
MAX_WORDS = 16384

#: n byte of ``ESC x`` per quality mode.
_QUALITY_N = {
    QUALITY_DRAFT: 0,
    QUALITY_NORMAL: 1,
    QUALITY_HIGH: 2,
}


def model_for_width(width_dots: int) -> str:
    '''Pick the printer model that fits a given label width.

    Args:
        width_dots: Label width in print dots.

    Returns:
        The matching model identifier from :data:`PRINT_MODELS`.

    Raises:
        ValueError: If the width fits neither model.
    '''
    if width_dots <= WIDTH_DOTS_G:
        return MODEL_TPTCM60
    if width_dots <= WIDTH_DOTS_H:
        return MODEL_TPTCM112
    raise ValueError(
        f"Label width {width_dots} dots exceeds the 832-dot print head"
    )


def words_per_line(model: str) -> int:
    '''Graphic page words per dotline for a printer model.

    Args:
        model: One of :data:`PRINT_MODELS`.

    Returns:
        28 for the G model, 52 for the H model.
    '''
    return WORDS_PER_LINE_G if model == MODEL_TPTCM60 else WORDS_PER_LINE_H


def page_lines(model: str) -> int:
    '''Graphic page height in dotlines for a printer model.

    Args:
        model: One of :data:`PRINT_MODELS`.

    Returns:
        585 for the G model, 315 for the H model.
    '''
    return PAGE_LINES_G if model == MODEL_TPTCM60 else PAGE_LINES_H


def pack_graphic_page(bitmap: np.ndarray, model: str) -> bytes:
    '''Pack a black/white bitmap into the ESC FD raster payload.

    Each dotline becomes ``words_per_line(model)`` 16-bit words, MSB of
    the word being the leftmost dot; rows are padded with white to the
    full print width.

    Args:
        bitmap: Bool array (H, W); True means an ink (black) dot.
        model: One of :data:`PRINT_MODELS`.

    Returns:
        The raw raster bytes ready to follow ``ESC FD nL nH``.

    Raises:
        ValueError: If the bitmap is wider than the print head or taller
            than the graphic page, or the word count exceeds 16384.
    '''
    if bitmap.ndim != 2 or bitmap.dtype != np.bool_:
        raise ValueError("bitmap must be a 2-D bool array")

    max_width = WIDTH_DOTS_G if model == MODEL_TPTCM60 else WIDTH_DOTS_H
    if bitmap.shape[1] > max_width:
        raise ValueError(
            f"bitmap width {bitmap.shape[1]} exceeds the {max_width}-dot"
            " print head of " + model
        )
    if bitmap.shape[0] > page_lines(model):
        raise ValueError(
            f"bitmap height {bitmap.shape[0]} exceeds the {page_lines(model)}"
            "-dotline graphic page of " + model
        )

    wpl = words_per_line(model)
    padded = np.zeros(
        (bitmap.shape[0], wpl * 16), dtype=np.bool_
    )
    padded[:, : bitmap.shape[1]] = bitmap

    # (H, W) bool -> (H, wpl, 16) bits, first bit = MSB of the word.
    words = padded.reshape(bitmap.shape[0], wpl, 16)
    weights = 1 << np.arange(15, -1, -1, dtype=np.uint16)
    word_values = (words.astype(np.uint16) * weights).sum(
        axis=-1, dtype=np.uint16
    )  # (H, wpl)

    raster = word_values.astype(">u2").tobytes()

    num_words = word_values.size
    if num_words > MAX_WORDS:
        raise ValueError(
            f"graphic page needs {num_words} words, the printer accepts"
            f" at most {MAX_WORDS}"
        )
    return raster


def build_label_stream(
    bitmap: np.ndarray,
    quality: str = QUALITY_HIGH,
    finish: str = FINISH_FEED,
    copies: int = 1,
    model: str | None = None,
) -> bytes:
    '''Build the full ESC/POS payload that prints a label ``copies`` times.

    One copy is ``ESC @`` + ``ESC x n`` + ``ESC FD`` raster +
    ``ESC FA`` (print ram bank from dotline 0 for H lines) + ``LF``,
    plus the optional cut command; copies simply repeat the block, each
    starting with its own ``ESC @`` reset.

    Args:
        bitmap: Bool array (H, W); True means an ink (black) dot.
        quality: One of :data:`QUALITY_MODES`.
        finish: One of :data:`FINISH_MODES`.
        copies: Number of label repetitions (>= 1).
        model: Printer model; inferred from the bitmap width when None.

    Returns:
        The raw byte stream to hand to the transport.

    Raises:
        ValueError: On invalid arguments (see :func:`pack_graphic_page`).
    '''
    if model is None:
        model = model_for_width(bitmap.shape[1])
    elif model not in PRINT_MODELS:
        raise ValueError(f"unknown printer model: {model!r}")
    if quality not in _QUALITY_N:
        raise ValueError(f"unknown quality mode: {quality!r}")
    if finish not in FINISH_MODES:
        raise ValueError(f"unknown finish mode: {finish!r}")
    if copies < 1:
        raise ValueError("copies must be >= 1")

    raster = pack_graphic_page(bitmap, model)
    num_words = len(raster) // 2
    height = bitmap.shape[0]

    cut = b""
    if finish == FINISH_TOTAL_CUT:
        cut = b"\x1b\x69"
    elif finish == FINISH_PARTIAL_CUT:
        cut = b"\x1b\x6d"

    one_copy = (
        b"\x1b\x40"  # ESC @ — initialize
        + b"\x1b\x78" + bytes([_QUALITY_N[quality]])  # ESC x n — quality
        + b"\x1b\xfd"  # ESC FD — receive graphic page
        + bytes([num_words & 0xFF, num_words >> 8])
        + raster
        + b"\x1b\xfa"  # ESC FA — print ram bank, dotline 0, height lines
        + bytes([0x00, 0x00, 0x00, height >> 8, height & 0xFF])
        + b"\x0a"  # LF
        + cut
    )
    return one_copy * copies
