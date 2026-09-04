'''
File:   test_nodes.py
Brief:  Node-level tests for the torch-free label element nodes.
Author: Mistress-Lukutar
Date:   2026-09-03
Version: v0.1.0
'''

from __future__ import annotations

import json

import numpy as np
from comfyui_lukutar_pos.core.label import LabelDocument
from comfyui_lukutar_pos.nodes import NODE_CLASS_MAPPINGS
from comfyui_lukutar_pos.nodes.label_elements import (
    LabelBarcodeNode,
    LabelCanvasNode,
    LabelQRNode,
    LabelRectNode,
    LabelTextNode,
)


def _canvas(size: str = "60mm roll / 40mm label (448x320)") -> LabelDocument:
    return LabelCanvasNode().create(size)[0]


def test_all_nodes_expose_valid_input_types():
    """Every registered node answers INPUT_TYPES with a JSON spec.

    Regression: ComfyUI silently drops a node from /object_info when
    its INPUT_TYPES raises (Label Image once referenced a dithering
    constant through the wrong module).
    """
    assert len(NODE_CLASS_MAPPINGS) == 10
    for key, node_cls in NODE_CLASS_MAPPINGS.items():
        spec = node_cls.INPUT_TYPES()
        json.dumps(spec)
        assert "required" in spec, key
        assert len(node_cls.RETURN_TYPES) == len(node_cls.RETURN_NAMES), key
        assert callable(getattr(node_cls, node_cls.FUNCTION, None)), key


def test_canvas_presets():
    """Preset names map to their dot geometry."""
    doc = _canvas()
    assert (doc.width_dots, doc.height_dots) == (448, 320)
    big = LabelCanvasNode().create("custom", 832, 160)[0]
    assert (big.width_dots, big.height_dots) == (832, 160)


def test_text_node_chain():
    """Text node passes a new LABEL through with ink added."""
    doc = _canvas()
    out = LabelTextNode().draw(
        doc,
        text="ТЕСТ 123",
        font="",
        size_mm=4.0,
        x_mm=2.0,
        y_mm=2.0,
        anchor="top-left",
        align="left",
        line_spacing_mm=0.5,
        bold=0,
        ink="black",
    )[0]
    assert isinstance(out, LabelDocument)
    assert out.to_bitmap().sum() > doc.to_bitmap().sum()


def test_barcode_node_defaults():
    """A full barcode block draws within the label."""
    out = LabelBarcodeNode().draw(
        _canvas(),
        data="LukutaR-2026",
        symbology="CODE128",
        height_mm=10.0,
        module_dots=2,
        x_mm=3.0,
        y_mm=20.0,
        anchor="top-left",
        quiet_zone_modules=10,
        show_text=True,
        text_mm=2.5,
        ink="black",
    )[0]
    assert out.to_bitmap().any()


def test_qr_node_draws_square():
    """The QR block is square and sits at the anchor."""
    out = LabelQRNode().draw(
        _canvas(),
        data="https://example.com",
        module_dots=2,
        quiet_modules=4,
        ecc="m",
        x_mm=20.0,
        y_mm=10.0,
        anchor="top-left",
        ink="black",
    )[0]
    bitmap = out.to_bitmap()
    rows = np.nonzero(bitmap.any(axis=1))[0]
    cols = np.nonzero(bitmap.any(axis=0))[0]
    assert (rows[-1] - rows[0]) == (cols[-1] - cols[0])
    # 10mm/20mm anchor plus the 4-module * 2-dot quiet zone.
    assert rows[0] == 88 and cols[0] == 168


def test_rect_node_pass_through():
    """Frame drawing returns a fresh document of the same geometry."""
    doc = _canvas()
    out = LabelRectNode().draw(
        doc,
        x_mm=1.0,
        y_mm=1.0,
        width_mm=54.0,
        height_mm=38.0,
        thickness_dots=2,
        filled=False,
        ink="black",
    )[0]
    assert out is not doc
    assert (out.width_dots, out.height_dots) == (448, 320)
    assert out.to_bitmap().any()
