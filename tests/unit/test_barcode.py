'''
File:   test_barcode.py
Brief:  Structural and checksum tests for the barcode renderer.
Author: Mistress-Lukutar
Date:   2026-09-03
Version: v0.1.0
'''

from __future__ import annotations

import numpy as np
import pytest
from comfyui_lukutar_pos.core import barcode
from comfyui_lukutar_pos.core.barcode import (
    _ean8_checksum,
    _ean13_checksum,
    _upc_checksum,
)


def _modules_of(data: str, symbology: str) -> str:
    """Render at module_dots=1 and read the middle row back as bits."""
    render = barcode.render_barcode(
        data, symbology=symbology, height_dots=2, module_dots=1,
        quiet_zone_modules=0,
    )
    row = render.bitmap[0]
    return "".join("1" if dot else "0" for dot in row)


def test_ean13_checksum_known_value():
    """Wikipedia's example number 400638133393 has check digit 1."""
    assert _ean13_checksum("4006381333931"[:12]) == 1


def test_ean8_checksum_known_value():
    """EAN-8 96385074 is the GS1 spec example (check digit 4)."""
    assert _ean8_checksum("9638507") == 4


def test_upc_checksum_known_value():
    """UPC-A 036000291452 (the classic example) has check digit 2."""
    assert _upc_checksum("036000291452"[:11]) == 2


def test_ean13_module_layout():
    """95 modules: guards 101, middle 01010, and the parity pattern."""
    modules = _modules_of("4006381333931", "EAN-13")
    assert len(modules) == 95
    assert modules[:3] == "101"
    assert modules[45:50] == "01010"
    assert modules[-3:] == "101"


def test_ean13_hri_contains_computed_check():
    """Passing 12 digits yields the checksum appended in the HRI."""
    render = barcode.render_barcode("400638133393", symbology="EAN-13")
    assert render.hri_text == "4006381333931"


def test_ean8_module_layout():
    """67 modules with the standard guard structure."""
    modules = _modules_of("9638507", "EAN-8")
    assert len(modules) == 67
    assert modules[:3] == "101"
    assert modules[-3:] == "101"


def test_upc_module_layout():
    """UPC-A is 95 modules like EAN-13 with a leading zero."""
    modules = _modules_of("036000291452", "UPC-A")
    assert len(modules) == 95
    assert modules[:3] == "101"


def test_code128_structure_and_checksum():
    """11 modules per symbol, 13 for stop, correct check value."""
    modules = _modules_of("AB12", "CODE128")
    # start(11) + 4 symbols(11) + check(11) + 13-module stop
    assert len(modules) == 11 * 6 + 13
    render = barcode.render_barcode("AB12", symbology="CODE128")
    assert render.hri_text == "AB12"
    # Start B=104, A=33, B=34, 1=17, 2=18 -> check 328 mod 103 = 19
    assert (104 + 33 + 68 + 51 + 72) % 103 == 19


def test_code39_start_stop_and_separators():
    """Every CODE39 symbol is 15 modules with 100010111011101 guards."""
    modules = _modules_of("AB", "CODE39")
    edge = "100010111011101"
    assert modules.startswith(edge) and modules.endswith(edge)
    assert len(modules) == 15 * 4  # start + 2 chars + stop


def test_itf_layout():
    """4-module start, 14 modules per digit pair (2-of-5), 4-module stop."""
    modules = _modules_of("1234", "ITF")
    assert modules[:4] == "1010"
    assert modules[-4:] == "1101"
    assert len(modules) == 4 + 2 * 14 + 4


def test_codabar_wraps_start_stop():
    """Start/stop letters are required and dropped from the HRI."""
    render = barcode.render_barcode("A1234B", symbology="CODABAR")
    assert render.hri_text == "1234"
    with pytest.raises(ValueError, match="start"):
        barcode.render_barcode("1234B", symbology="CODABAR")
    with pytest.raises(ValueError, match="stop"):
        barcode.render_barcode("A1234", symbology="CODABAR")


def test_quiet_zone_and_scaling():
    """Quiet zones widen the bitmap; module_dots scale horizontally."""
    render = barcode.render_barcode(
        "1234", symbology="ITF", height_dots=10,
        module_dots=2, quiet_zone_modules=10,
    )
    base = len(_modules_of("1234", "ITF"))
    assert render.bitmap.shape == (10, (base + 20) * 2)
    assert render.bitmap.dtype == np.bool_


def test_input_validation():
    """Each symbology rejects data it cannot encode."""
    with pytest.raises(ValueError, match="digits"):
        barcode.render_barcode("12A4", symbology="EAN-13")
    with pytest.raises(ValueError, match="12 digits"):
        barcode.render_barcode("123", symbology="EAN-13")
    with pytest.raises(ValueError, match="even"):
        barcode.render_barcode("123", symbology="ITF")
    with pytest.raises(ValueError, match="CODE39"):
        barcode.render_barcode("abc*", symbology="CODE39")
    with pytest.raises(ValueError, match="empty"):
        barcode.render_barcode("   ", symbology="CODE128")
    with pytest.raises(ValueError, match="symbology"):
        barcode.render_barcode("123", symbology="AZTEC")
