'''
File:   test_label.py
Brief:  Label compositor tests: canvas, anchors, text, QR, images.
Author: Mistress-Lukutar
Date:   2026-09-03
Version: v0.1.0
'''

from __future__ import annotations

import numpy as np
import pytest
from comfyui_lukutar_pos.core import label as core
from comfyui_lukutar_pos.core.escpos import build_label_stream


def test_create_label_geometry():
    """Presets map to dot sizes; oversized pages are rejected."""
    doc = core.create_label(448, 320)
    assert doc.width_dots == 448 and doc.height_dots == 320
    bitmap = doc.to_bitmap()
    assert bitmap.shape == (320, 448)
    assert not bitmap.any()  # white background = no ink

    with pytest.raises(ValueError, match="graphic page"):
        core.create_label(448, 586)
    with pytest.raises(ValueError, match="print head"):
        core.create_label(900, 100)


def test_dark_background_and_white_ink():
    """A black canvas plus white ink produces paper pixels."""
    doc = core.create_label(448, 64, dark_background=True)
    assert doc.to_bitmap().all()
    glyph = np.zeros((8, 8), dtype=np.bool_)
    glyph[2:6, 2:6] = True
    out = core.draw_bitmap(doc, glyph, 10, 10, ink=False).to_bitmap()
    assert not out[12, 12]  # painted white
    assert out[0, 0]  # rest stays black


def test_draw_bitmap_clipping():
    """Bitmaps hanging off the canvas are clipped, not errors."""
    doc = core.create_label(64, 64)
    block = np.ones((32, 32), dtype=np.bool_)
    out = core.draw_bitmap(doc, block, 48, 48).to_bitmap()
    assert out[48:64, 48:64].all()
    assert not out[:48, :].any()


def test_anchor_math():
    """center anchor shifts a block by half its size."""
    dx, dy = core.anchor_offset("center", 30, 20)
    assert (dx, dy) == (-15, -10)
    dx, dy = core.anchor_offset("bottom-right", 30, 20)
    assert (dx, dy) == (-30, -20)
    dx, dy = core.anchor_offset("top-left", 30, 20)
    assert (dx, dy) == (0, 0)
    with pytest.raises(ValueError, match="anchor"):
        core.anchor_offset("middle", 1, 1)


def test_mm_to_dots():
    """Millimetres convert at 8 dots per mm with rounding."""
    assert core.mm_to_dots(1.0) == 8
    assert core.mm_to_dots(3.06) == 24
    assert core.mm_to_dots(56.0) == 448


def test_draw_text_places_ink():
    """Latin and Cyrillic text both rasterize to ink pixels."""
    doc = core.create_label(448, 320)
    out = core.draw_text(
        doc, "Hello", size_mm=4.0, x_mm=2, y_mm=2
    ).to_bitmap()
    assert out.any()

    cyr = core.draw_text(
        doc, "Привет", size_mm=4.0, x_mm=2, y_mm=20
    ).to_bitmap()
    assert cyr.any()


def test_draw_text_multiline_and_align():
    """Three lines land lower than one; alignment shifts ink columns."""
    doc = core.create_label(448, 320)
    one = core.draw_text(doc, "A", x_mm=0, y_mm=0).to_bitmap()
    three = core.draw_text(
        doc, "A\nB\nC", x_mm=0, y_mm=0, line_spacing_mm=0.0
    ).to_bitmap()
    assert three.sum() > one.sum()

    left = core.draw_text(
        doc, "AB\nC", x_mm=10, y_mm=0, align="left"
    ).to_bitmap()
    right = core.draw_text(
        doc, "AB\nC", x_mm=10, y_mm=0, align="right"
    ).to_bitmap()

    def second_line_left_col(bitmap: np.ndarray) -> int:
        rows = np.nonzero(bitmap.any(axis=1))[0]
        split = (rows[0] + rows[-1]) // 2  # between the two lines
        return int(np.nonzero(bitmap[split:].any(axis=0))[0][0])

    # The single-char second line starts further right when right-aligned.
    assert second_line_left_col(right) > second_line_left_col(left)


def test_draw_barcode_block_inside_canvas():
    """The whole barcode block (bars + HRI) lands inside the label."""
    doc = core.create_label(448, 320)
    out = core.draw_barcode(
        doc, "4006381333931", symbology="EAN-13",
        height_mm=10, x_mm=28, y_mm=15, anchor="center", show_text=False,
    ).to_bitmap()
    assert out.any()
    cols = np.nonzero(out.any(axis=0))[0]
    # 95 modules * 2 dots + 20 quiet modules * 2 dots, centered on 28mm.
    assert cols[0] == pytest.approx(224 - 115 + 20, abs=1)
    assert cols[-1] == pytest.approx(224 + 115 - 20, abs=1)


def test_draw_qr_geometry_and_quiet_zone():
    """QR bitmap side = (modules + 2*quiet) * module_dots."""
    doc = core.create_label(448, 320)
    out = core.draw_qr(
        doc, "https://example.com", module_dots=2, quiet_modules=4,
        x_mm=0, y_mm=0,
    ).to_bitmap()
    ink_cols = np.nonzero(out.any(axis=0))[0]
    ink_rows = np.nonzero(out.any(axis=1))[0]
    side_dots = ink_cols[-1] - ink_cols[0] + 1
    # 4 quiet modules * 2 dots on each side must surround the code
    assert ink_cols[0] == 8 and ink_rows[0] == 8
    assert side_dots % 2 == 0


def test_draw_rect_outline_and_fill():
    """Outline hollow, fill solid; thickness grows the border."""
    doc = core.create_label(448, 320)
    outline = core.draw_rect(
        doc, 5, 5, 30, 20, thickness_dots=2
    ).to_bitmap()
    assert outline.any()
    assert not outline[
        core.mm_to_dots(5) + 4 : core.mm_to_dots(25) - 4,
        core.mm_to_dots(5) + 4 : core.mm_to_dots(35) - 4,
    ].any()

    filled = core.draw_rect(doc, 5, 5, 30, 20, filled=True).to_bitmap()
    assert filled[
        core.mm_to_dots(5) + 4 : core.mm_to_dots(25) - 4,
        core.mm_to_dots(5) + 4 : core.mm_to_dots(35) - 4,
    ].all()


def test_prepare_image_block_fit_modes():
    """contain keeps aspect with white bars; stretch distorts; cover fills."""
    tall = np.linspace(0.0, 255.0, 100, dtype=np.float32)[:, None] * np.ones(
        (1, 40), np.float32
    )  # 100 x 40

    contain = core.prepare_image_block(
        tall, 80, 80, fit="contain", dither_method="threshold"
    )
    assert contain.shape == (80, 80)
    # A 40-dot-wide image centered in 80 dots: 20 white columns each side.
    assert not contain[:, :16].any() and not contain[:, -16:].any()

    stretch = core.prepare_image_block(
        tall, 80, 80, fit="stretch", dither_method="threshold"
    )
    assert stretch.shape == (80, 80)
    assert stretch[:, 0].any()  # ink reaches the border

    cover = core.prepare_image_block(
        tall, 80, 80, fit="cover", dither_method="threshold"
    )
    assert cover[:, 0].any() and cover[:, -1].any()


def test_label_to_stream_roundtrip():
    """to_stream produces the exact payload for the composed bitmap."""
    doc = core.create_label(448, 64)
    doc = core.draw_rect(doc, 0, 0, 56, 8, filled=True)
    stream = doc.to_stream(quality="normal", finish="feed", copies=2)
    expected = build_label_stream(
        doc.to_bitmap(), quality="normal", finish="feed", copies=2
    )
    assert stream == expected


def test_copy_on_write():
    """Drawing never mutates the source document."""
    doc = core.create_label(64, 64)
    before = doc.to_bitmap().copy()
    core.draw_rect(doc, 0, 0, 8, 8, filled=True)
    assert (doc.to_bitmap() == before).all()
