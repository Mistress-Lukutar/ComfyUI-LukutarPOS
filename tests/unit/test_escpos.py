'''
File:   test_escpos.py
Brief:  Byte-level tests of the ESC/POS graphic page protocol.
Author: Mistress-Lukutar
Date:   2026-09-03
Version: v0.1.0
'''

from __future__ import annotations

import numpy as np
import pytest
from comfyui_lukutar_pos.core import escpos


def test_pack_single_dot_msb_first():
    """The first dot of a row lands in the MSB of the first word."""
    bitmap = np.zeros((1, 448), dtype=np.bool_)
    bitmap[0, 0] = True
    raster = escpos.pack_graphic_page(bitmap, escpos.MODEL_TPTCM60)
    assert len(raster) == 2 * escpos.WORDS_PER_LINE_G
    assert raster[0] == 0x80  # dot 0 -> bit 15 of word 0
    assert raster[1] == 0x00


def test_pack_sixteenth_dot_is_lsb():
    """Dot 15 of a row lands in the LSB of the first word."""
    bitmap = np.zeros((1, 16), dtype=np.bool_)
    bitmap[0, 15] = True
    raster = escpos.pack_graphic_page(bitmap, escpos.MODEL_TPTCM60)
    assert raster[0] == 0x00
    assert raster[1] == 0x01  # low byte of word 0


def test_pack_pads_narrow_rows_to_full_width():
    """Rows narrower than the head are padded with white words."""
    bitmap = np.zeros((2, 3), dtype=np.bool_)
    bitmap[:, :] = True
    raster = escpos.pack_graphic_page(bitmap, escpos.MODEL_TPTCM60)
    # 2 rows x 28 words x 2 bytes, all-white beyond each row's first word.
    assert len(raster) == 2 * 28 * 2
    assert raster[0] == 0xE0  # 3 black dots in the MSBs of row 0
    assert raster[56] == 0xE0  # same for row 1
    expected = bytearray(len(raster))
    expected[0] = expected[56] = 0xE0
    assert raster == bytes(expected)


def test_pack_112mm_model_uses_52_words():
    """The H model packs 52 words (832 dots) per dotline."""
    bitmap = np.zeros((1, 832), dtype=np.bool_)
    raster = escpos.pack_graphic_page(bitmap, escpos.MODEL_TPTCM112)
    assert len(raster) == 2 * escpos.WORDS_PER_LINE_H


def test_pack_rejects_oversize():
    """Geometry violations raise instead of producing a broken stream."""
    with pytest.raises(ValueError, match="print head"):
        escpos.pack_graphic_page(
            np.zeros((1, 449), dtype=np.bool_), escpos.MODEL_TPTCM60
        )
    with pytest.raises(ValueError, match="graphic page"):
        escpos.pack_graphic_page(
            np.zeros((586, 448), dtype=np.bool_), escpos.MODEL_TPTCM60
        )


def test_stream_layout_matches_working_script():
    """Full payload reproduces the proven test.py byte layout."""
    height = 320
    bitmap = np.zeros((height, 448), dtype=np.bool_)
    stream = escpos.build_label_stream(bitmap, copies=1)
    num_words = height * 28

    assert stream[:2] == b"\x1b\x40"  # ESC @
    assert stream[2:5] == b"\x1b\x78\x02"  # ESC x 2 (high quality)
    assert stream[5:7] == b"\x1b\xfd"  # ESC FD
    assert stream[7] == num_words & 0xFF
    assert stream[8] == num_words >> 8
    raster_len = num_words * 2
    assert stream[9 + raster_len : 11 + raster_len] == b"\x1b\xfa"
    tail = stream[11 + raster_len :]
    # n=0 (ram bank), xH=0, xL=0, yH=1, yL=0x40 (320 lines), then LF.
    assert tail == b"\x00\x00\x00\x01\x40\x0a"


def test_stream_quality_and_finish_variants():
    """ESC x n and the cut bytes follow the selected modes."""
    bitmap = np.zeros((16, 448), dtype=np.bool_)
    base = escpos.build_label_stream(
        bitmap, quality=escpos.QUALITY_DRAFT, finish=escpos.FINISH_NONE
    )
    assert base[2:5] == b"\x1b\x78\x00"
    assert not base.endswith(b"\x1bi") and not base.endswith(b"\x1bm")

    total = escpos.build_label_stream(
        bitmap, finish=escpos.FINISH_TOTAL_CUT
    )
    assert total.endswith(b"\x1bi")
    partial = escpos.build_label_stream(
        bitmap, finish=escpos.FINISH_PARTIAL_CUT
    )
    assert partial.endswith(b"\x1bm")


def test_copies_repeat_the_block():
    """Each copy is a full standalone payload starting with ESC @."""
    bitmap = np.zeros((16, 448), dtype=np.bool_)
    one = escpos.build_label_stream(bitmap, copies=1)
    three = escpos.build_label_stream(bitmap, copies=3)
    assert three == one * 3
    assert three.count(b"\x1b\x40") == 3


def test_model_inference_from_width():
    """Width <= 448 selects the G model, up to 832 the H model."""
    assert escpos.model_for_width(448) == escpos.MODEL_TPTCM60
    assert escpos.model_for_width(832) == escpos.MODEL_TPTCM112
    with pytest.raises(ValueError, match="832"):
        escpos.model_for_width(900)


def test_stream_validation():
    """Unknown enum values and bad copies are rejected."""
    bitmap = np.zeros((16, 448), dtype=np.bool_)
    with pytest.raises(ValueError, match="quality"):
        escpos.build_label_stream(bitmap, quality="ultra")
    with pytest.raises(ValueError, match="finish"):
        escpos.build_label_stream(bitmap, finish="fold")
    with pytest.raises(ValueError, match="copies"):
        escpos.build_label_stream(bitmap, copies=0)
    with pytest.raises(ValueError, match="model"):
        escpos.build_label_stream(bitmap, model="TPTCM999")
