'''
File:   barcode.py
Brief:  Rasterize 1-D barcodes into 1-bit label bitmaps.
Author: Mistress-Lukutar
Date:   2026-09-03
Version: v0.1.0

Builds black/white module matrices for the symbologies the ESC/POS
``GS k`` command documents (UPC-A, EAN-13, EAN-8, CODE39, ITF, CODABAR,
CODE93, CODE128) — rendered into the label bitmap instead of the native
command so the printed label matches the on-screen preview exactly.

Pattern tables and charset switching come from python-barcode's
``barcode.charsets`` modules (MIT); checksums and the module layout are
computed here so every symbology funnels into one renderer.
'''

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from barcode import get_barcode_class
from barcode.charsets import codabar as _cdb
from barcode.charsets import code39 as _c39
from barcode.charsets import code128 as _c128
from barcode.charsets import ean as _ean
from barcode.charsets import itf as _itf

#: Code 128 (automatic code set B/C switching).
SYMBLOGY_CODE128 = "CODE128"
#: EAN-13 (12 digits + computed checksum).
SYMBLOGY_EAN13 = "EAN-13"
#: EAN-8 (7 digits + computed checksum).
SYMBLOGY_EAN8 = "EAN-8"
#: UPC-A (11 digits + computed checksum).
SYMBLOGY_UPC_A = "UPC-A"
#: Code 39 (uppercase alphanumerics and -.$/+% space).
SYMBLOGY_CODE39 = "CODE39"
#: Interleaved 2 of 5 (even number of digits).
SYMBLOGY_ITF = "ITF"
#: Codabar (digits, wrapped in A-D start/stop letters).
SYMBLOGY_CODABAR = "CODABAR"
#: Selectable barcode symbologies.
BARCODE_TYPES: tuple[str, ...] = (
    SYMBLOGY_CODE128,
    SYMBLOGY_EAN13,
    SYMBLOGY_EAN8,
    SYMBLOGY_UPC_A,
    SYMBLOGY_CODE39,
    SYMBLOGY_ITF,
    SYMBLOGY_CODABAR,
)

#: White modules added left and right of the bars (scanner quiet zone).
DEFAULT_QUIET_MODULES = 10


@dataclass(frozen=True)
class BarcodeRender:
    '''A rendered barcode plus the text shown under it (HRI).

    Attributes:
        bitmap: Bool array (height_dots, width_dots); True = ink.
        hri_text: Human-readable interpretation string.
    '''

    bitmap: np.ndarray
    hri_text: str


def _ean13_checksum(digits: str) -> int:
    '''EAN-13 check digit: weight 1/3 alternating from the left.

    Args:
        digits: Exactly 12 digits.

    Returns:
        The check digit (0-9).
    '''
    total = sum(
        int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits)
    )
    return (10 - total % 10) % 10


def _ean8_checksum(digits: str) -> int:
    '''EAN-8 check digit: weight 3/1 alternating from the left.

    Args:
        digits: Exactly 7 digits.

    Returns:
        The check digit (0-9).
    '''
    total = sum(
        int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(digits)
    )
    return (10 - total % 10) % 10


def _upc_checksum(digits: str) -> int:
    '''UPC-A check digit: weight 3/1 alternating from the left.

    Args:
        digits: Exactly 11 digits.

    Returns:
        The check digit (0-9).
    '''
    total = sum(
        int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(digits)
    )
    return (10 - total % 10) % 10


def _digits_only(data: str, symbology: str) -> str:
    '''Validate that the data is all decimal digits.

    Args:
        data: Raw user data.
        symbology: Name used in the error message.

    Returns:
        The stripped digit string.

    Raises:
        ValueError: When the data contains non-digit characters.
    '''
    stripped = data.strip()
    if not stripped or not stripped.isdigit():
        raise ValueError(f"{symbology} data must be digits only: {data!r}")
    return stripped


def _modules_ean13(data: str) -> tuple[str, str]:
    '''Encode EAN-13 into its 95-module bit string.

    Args:
        data: 12 digits, or 13 (the check digit is recomputed).

    Returns:
        (module string, HRI text with the computed check digit).
    '''
    digits = _digits_only(data, SYMBLOGY_EAN13)
    if len(digits) not in (12, 13):
        raise ValueError("EAN-13 needs 12 digits (checksum is computed)")
    payload = digits[:12]
    check = _ean13_checksum(payload)
    full = payload + str(check)

    parity = _ean.LEFT_PATTERN[int(full[0])]
    left = "".join(
        _ean.CODES[parity[i]][int(full[i + 1])] for i in range(6)
    )
    right = "".join(_ean.CODES["C"][int(d)] for d in full[7:])
    modules = _ean.EDGE + left + _ean.MIDDLE + right + _ean.EDGE
    return modules, full


def _modules_ean8(data: str) -> tuple[str, str]:
    '''Encode EAN-8 into its 67-module bit string.

    Args:
        data: 7 digits, or 8 (the check digit is recomputed).

    Returns:
        (module string, HRI text with the computed check digit).
    '''
    digits = _digits_only(data, SYMBLOGY_EAN8)
    if len(digits) not in (7, 8):
        raise ValueError("EAN-8 needs 7 digits (checksum is computed)")
    payload = digits[:7]
    check = _ean8_checksum(payload)
    full = payload + str(check)

    left = "".join(_ean.CODES["A"][int(d)] for d in full[:4])
    right = "".join(_ean.CODES["C"][int(d)] for d in full[4:])
    modules = _ean.EDGE + left + _ean.MIDDLE + right + _ean.EDGE
    return modules, full


def _modules_upc_a(data: str) -> tuple[str, str]:
    '''Encode UPC-A into its 95-module bit string.

    Args:
        data: 11 digits, or 12 (the check digit is recomputed).

    Returns:
        (module string, HRI text with the computed check digit).
    '''
    digits = _digits_only(data, SYMBLOGY_UPC_A)
    if len(digits) not in (11, 12):
        raise ValueError("UPC-A needs 11 digits (checksum is computed)")
    payload = digits[:11]
    check = _upc_checksum(payload)
    full = payload + str(check)

    left = "".join(_ean.CODES["A"][int(d)] for d in full[:6])
    right = "".join(_ean.CODES["C"][int(d)] for d in full[6:])
    modules = _ean.EDGE + left + _ean.MIDDLE + right + _ean.EDGE
    return modules, full


def _modules_code128(data: str) -> tuple[str, str]:
    '''Encode CODE128 with automatic code set selection.

    python-barcode resolves the B/C switching and produces the code
    value sequence (start code, payload); the check value and the
    bit patterns are applied here.

    Args:
        data: Arbitrary ASCII text.

    Returns:
        (module string, HRI text — the data itself).
    '''
    stripped = data.strip()
    if not stripped:
        raise ValueError("CODE128 data must not be empty")
    bc = get_barcode_class("code128")(stripped)
    bc.build()
    codes = list(bc.encoded)  # start code + payload values

    check = codes[0]
    for position, value in enumerate(codes[1:], start=1):
        check = (check + position * value) % 103
    codes.append(check)

    modules = "".join(_c128.CODES[v] for v in codes)
    # python-barcode's STOP omits the two-module termination bar; the
    # standard CODE128 stop is 13 modules.
    modules += _c128.STOP + "11"
    return modules, stripped


def _modules_code39(data: str) -> tuple[str, str]:
    '''Encode CODE39 with start/stop asterisks.

    Args:
        data: Characters from the CODE39 set (case-insensitive).

    Returns:
        (module string, HRI text — the data itself).
    '''
    stripped = data.strip().upper()
    if not stripped:
        raise ValueError("CODE39 data must not be empty")
    unknown = [c for c in stripped if c not in _c39.MAP]
    if unknown:
        raise ValueError(
            f"CODE39 cannot encode {unknown!r}; allowed: 0-9 A-Z - . space"
            " $ / + %"
        )
    modules = (
        _c39.EDGE
        + "".join(_c39.MAP[c][1] for c in stripped)
        + _c39.EDGE
    )
    return modules, stripped


def _modules_itf(data: str) -> tuple[str, str]:
    '''Encode Interleaved 2 of 5.

    Args:
        data: An even number of digits.

    Returns:
        (module string, HRI text — the digits themselves).
    '''
    digits = _digits_only(data, SYMBLOGY_ITF)
    if len(digits) % 2 != 0:
        raise ValueError("ITF needs an even number of digits")

    def widths(pattern: str) -> list[int]:
        return [2 if ch == "W" else 1 for ch in pattern]

    modules_list: list[str] = []
    for i in range(0, len(digits), 2):
        bars = widths(_itf.CODES[int(digits[i])])
        spaces = widths(_itf.CODES[int(digits[i + 1])])
        for bar, space in zip(bars, spaces, strict=True):
            modules_list.append("1" * bar + "0" * space)

    start = "1010"  # NnNn — narrow bar, gap, bar, gap
    stop = "1101"  # WnN — wide bar, narrow gap, narrow bar
    return start + "".join(modules_list) + stop, digits


def _modules_codabar(data: str) -> tuple[str, str]:
    '''Encode Codabar with mandatory start/stop letters.

    Args:
        data: Digits and symbols, wrapped in A-D (e.g. ``A1234B``).

    Returns:
        (module string, HRI text without the start/stop letters).
    '''
    stripped = data.strip().upper()
    if len(stripped) < 3 or stripped[0] not in _cdb.STARTSTOP:
        raise ValueError(
            "CODABAR data must start with a start letter A-D, e.g. A1234B"
        )
    if stripped[-1] not in _cdb.STARTSTOP:
        raise ValueError(
            "CODABAR data must end with a stop letter A-D, e.g. A1234B"
        )
    for ch in stripped[1:-1]:
        if ch not in _cdb.CODES:
            raise ValueError(f"CODABAR cannot encode {ch!r}")

    def modules_for(char: str) -> str:
        table = _cdb.STARTSTOP if char in _cdb.STARTSTOP else _cdb.CODES
        return "".join(
            ("1" if i % 2 == 0 else "0") * (2 if ch_ in "Ww" else 1)
            for i, ch_ in enumerate(table[char])
        )

    modules = "".join(modules_for(ch) for ch in stripped)
    return modules, stripped[1:-1]


_MODULE_BUILDERS = {
    SYMBLOGY_CODE128: _modules_code128,
    SYMBLOGY_EAN13: _modules_ean13,
    SYMBLOGY_EAN8: _modules_ean8,
    SYMBLOGY_UPC_A: _modules_upc_a,
    SYMBLOGY_CODE39: _modules_code39,
    SYMBLOGY_ITF: _modules_itf,
    SYMBLOGY_CODABAR: _modules_codabar,
}


def render_barcode(
    data: str,
    symbology: str = SYMBLOGY_CODE128,
    height_dots: int = 80,
    module_dots: int = 2,
    quiet_zone_modules: int = DEFAULT_QUIET_MODULES,
) -> BarcodeRender:
    '''Render one barcode as a 1-bit bitmap.

    Args:
        data: Payload; validation depends on the symbology.
        symbology: One of :data:`BARCODE_TYPES`.
        height_dots: Bar height in print dots.
        module_dots: Width of one module in print dots (2 is a safe
            default for 203 DPI scanners).
        quiet_zone_modules: White modules on each side of the bars.

    Returns:
        The rendered bitmap (True = ink) and the HRI text.

    Raises:
        ValueError: On an unknown symbology or invalid data.
    '''
    if symbology not in _MODULE_BUILDERS:
        raise ValueError(f"unknown barcode symbology: {symbology!r}")
    if height_dots < 1:
        raise ValueError("height_dots must be >= 1")
    if module_dots < 1:
        raise ValueError("module_dots must be >= 1")

    modules, hri = _MODULE_BUILDERS[symbology](data)

    quiet = "0" * quiet_zone_modules
    bits = np.frombuffer(
        (quiet + modules + quiet).encode("ascii"), dtype=np.uint8
    ) - ord("0")
    one_row = np.repeat(bits.astype(np.bool_), module_dots)
    bitmap = np.tile(one_row, (height_dots, 1))
    return BarcodeRender(bitmap=np.ascontiguousarray(bitmap), hri_text=hri)
