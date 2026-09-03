'''
File:   label.py
Brief:  Label document model and raster compositor (203 DPI, 1-bit).
Author: Mistress-Lukutar
Date:   2026-09-03
Version: v0.1.0

A label is a white 1-bit canvas the width of the print head
(448 dots on the 60 mm TPTCM60, 832 on the 112 mm TPTCM112).
Every drawing operation is copy-on-write: it returns a new
:class:`LabelDocument`, so ComfyUI's node graph stays a pure pipeline
and any intermediate state can be previewed.

Element positions and sizes are given in millimetres and converted at
8 dots/mm (203 DPI); x grows right, y grows down, and the ``anchor``
9-grid names which point of a block the (x, y) millimetre coordinates
refer to.
'''

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .barcode import (
    DEFAULT_QUIET_MODULES,
    SYMBLOGY_CODE128,
    render_barcode,
)
from .dithering import (
    DITHER_FLOYD_STEINBERG,
    adjust_tone,
    dither,
)
from .escpos import build_label_stream, model_for_width, page_lines

#: Print head resolution: 8 dots per mm (203 DPI).
DOTS_PER_MM = 8.0

#: 60 mm roll, 40 mm feed — the label the standalone test script used.
LABEL_60x40 = "60mm roll / 40mm label (448x320)"
#: 60 mm roll, 30 mm feed.
LABEL_60x30 = "60mm roll / 30mm label (448x240)"
#: 60 mm roll, 20 mm feed.
LABEL_60x20 = "60mm roll / 20mm label (448x160)"
#: 60 mm roll, 60 mm feed.
LABEL_60x60 = "60mm roll / 60mm label (448x480)"
#: 60 mm roll, full graphic page height.
LABEL_60_FULL = "60mm roll / full page (448x585)"
#: 112 mm roll, 30 mm feed.
LABEL_112x30 = "112mm roll / 30mm label (832x240)"
#: 112 mm roll, 20 mm feed.
LABEL_112x20 = "112mm roll / 20mm label (832x160)"
#: 112 mm roll, full graphic page height.
LABEL_112_FULL = "112mm roll / full page (832x315)"
#: Custom size from the width/height widgets.
LABEL_CUSTOM = "custom"
#: Selectable label presets; value -> (width_dots, height_dots).
LABEL_SIZES: dict[str, tuple[int, int] | None] = {
    LABEL_60x40: (448, 320),
    LABEL_60x30: (448, 240),
    LABEL_60x20: (448, 160),
    LABEL_60x60: (448, 480),
    LABEL_60_FULL: (448, 585),
    LABEL_112x30: (832, 240),
    LABEL_112x20: (832, 160),
    LABEL_112_FULL: (832, 315),
    LABEL_CUSTOM: None,
}

#: The nine anchor points of a block.
ANCHORS: tuple[str, ...] = (
    "top-left",
    "top-center",
    "top-right",
    "middle-left",
    "center",
    "middle-right",
    "bottom-left",
    "bottom-center",
    "bottom-right",
)

#: Contain: fit fully inside the box, keeping the aspect ratio.
FIT_CONTAIN = "contain"
#: Cover: fill the box, keeping the aspect ratio, crop the overflow.
FIT_COVER = "cover"
#: Stretch: exactly the box, aspect ratio ignored.
FIT_STRETCH = "stretch"
#: Selectable image fit modes.
FIT_MODES: tuple[str, ...] = (FIT_CONTAIN, FIT_COVER, FIT_STRETCH)

#: Bundled fallback fonts, also usable by name in the font widget.
BUNDLED_FONTS: dict[str, str] = {
    "": "DejaVuSans.ttf",
    "default": "DejaVuSans.ttf",
    "bold": "DejaVuSans-Bold.ttf",
    "mono": "DejaVuSansMono.ttf",
}
_FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"


def mm_to_dots(value_mm: float) -> int:
    '''Convert millimetres to whole print dots (8 dots/mm).

    Args:
        value_mm: A length in millimetres.

    Returns:
        The rounded dot count.
    '''
    return int(round(value_mm * DOTS_PER_MM))


def anchor_offset(anchor: str, width: int, height: int) -> tuple[int, int]:
    '''Offset of a block's top-left corner for an anchor point.

    Args:
        anchor: One of :data:`ANCHORS` (e.g. ``center``).
        width: Block width in dots.
        height: Block height in dots.

    Returns:
        (dx, dy) to add to the anchor coordinates to get the top-left
        corner of the block.

    Raises:
        ValueError: On an unknown anchor name.
    '''
    if anchor not in ANCHORS:
        raise ValueError(f"unknown anchor: {anchor!r}")
    row, _, column = anchor.partition("-")
    if not column:  # the bare "center" anchor
        row = column = "center"
    if row == "center":
        row = "middle"
    dx = {
        "left": 0,
        "center": -width // 2,
        "right": -width,
    }[column]
    dy = {
        "top": 0,
        "middle": -height // 2,
        "bottom": -height,
    }[row]
    return dx, dy


@dataclass(frozen=True)
class LabelDocument:
    '''An immutable 1-bit label canvas.

    Attributes:
        image: PIL image, mode ``1`` (0 = black ink, 255 = white paper).
        width_dots: Canvas width in print dots.
        height_dots: Canvas height in print dots.
    '''

    image: Image.Image = field(repr=False)
    width_dots: int = 0
    height_dots: int = 0

    def to_bitmap(self) -> np.ndarray:
        '''The canvas as a bool array with True meaning ink.

        Returns:
            Bool array (height_dots, width_dots).
        '''
        return np.logical_not(np.asarray(self.image))

    def to_gray(self) -> np.ndarray:
        '''The canvas as float32 gray levels (0 = ink, 255 = paper).

        Returns:
            Float32 array (height_dots, width_dots) in [0, 255].
        '''
        return np.asarray(self.image.convert("L"), dtype=np.float32)

    def to_stream(
        self,
        quality: str,
        finish: str,
        copies: int = 1,
        model: str | None = None,
    ) -> bytes:
        '''The ESC/POS payload that prints this label.

        Args:
            quality: One of :data:`escpos.QUALITY_MODES`.
            finish: One of :data:`escpos.FINISH_MODES`.
            copies: Number of label repetitions.
            model: Printer model; inferred from the width when None.

        Returns:
            Raw ESC/POS bytes for the transport.
        '''
        return build_label_stream(
            self.to_bitmap(), quality=quality, finish=finish,
            copies=copies, model=model,
        )


def create_label(
    width_dots: int, height_dots: int, dark_background: bool = False
) -> LabelDocument:
    '''Create a fresh label canvas.

    Args:
        width_dots: Canvas width; must fit a print head (448/832).
        height_dots: Canvas height; must fit the graphic page.
        dark_background: Start black instead of white (for white ink).

    Returns:
        The new document.

    Raises:
        ValueError: When the size exceeds the printer geometry.
    '''
    model = model_for_width(width_dots)
    if width_dots < 1 or height_dots < 1:
        raise ValueError("label size must be positive")
    if height_dots > page_lines(model):
        raise ValueError(
            f"height {height_dots} exceeds the {page_lines(model)}-dotline"
            " graphic page of " + model
        )
    color = 0 if dark_background else 255
    image = Image.new("1", (width_dots, height_dots), color)
    return LabelDocument(
        image=image, width_dots=width_dots, height_dots=height_dots
    )


def load_font(font: str, size_dots: int) -> ImageFont.FreeTypeFont:
    '''Resolve a font spec into a scalable PIL font.

    Args:
        font: One of the :data:`BUNDLED_FONTS` names (``""``, ``bold``,
            ``mono``), a file name inside the pack's ``assets/fonts``,
            or an absolute path to a ``.ttf``/``.otf``.
        size_dots: Pixel (dot) size of the glyphs.

    Returns:
        The loaded font.

    Raises:
        ValueError: When nothing can be loaded for the spec.
    '''
    key = font.strip().lower()
    candidates: list[Path] = []
    if key in BUNDLED_FONTS:
        candidates.append(_FONTS_DIR / BUNDLED_FONTS[key])
    else:
        as_path = Path(font)
        if as_path.is_absolute():
            candidates.append(as_path)
        else:
            candidates.append(_FONTS_DIR / font)
            candidates.append(_FONTS_DIR / f"{font}.ttf")
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size_dots)
    raise ValueError(
        f"cannot load font {font!r}; use '', 'bold', 'mono', a file in"
        f" {_FONTS_DIR} or an absolute path"
    )


def _ink_mask(bitmap: np.ndarray) -> Image.Image:
    '''Bool ink array (True = paint) as a PIL L-mode mask.'''
    return Image.fromarray(
        np.where(bitmap, 255, 0).astype(np.uint8), mode="L"
    )


def draw_bitmap(
    label: LabelDocument,
    bitmap: np.ndarray,
    x: int,
    y: int,
    ink: bool = True,
) -> LabelDocument:
    '''Paint a bool bitmap onto the canvas (True pixels only).

    Regions outside the canvas are clipped.

    Args:
        label: The document to copy and modify.
        bitmap: Bool array (H, W); True means paint.
        x: Left edge in dots.
        y: Top edge in dots.
        ink: True paints black, False paints white (erase).

    Returns:
        The new document.
    '''
    canvas = label.image.copy()
    canvas.paste(0 if ink else 255, (x, y), _ink_mask(bitmap))
    return LabelDocument(
        image=canvas, width_dots=label.width_dots,
        height_dots=label.height_dots,
    )


def draw_text(
    label: LabelDocument,
    text: str,
    font: str = "",
    size_mm: float = 3.0,
    x_mm: float = 0.0,
    y_mm: float = 0.0,
    anchor: str = "top-left",
    align: str = "left",
    line_spacing_mm: float = 0.5,
    bold: int = 0,
    ink: bool = True,
) -> LabelDocument:
    '''Draw (possibly multiline) text onto the canvas.

    Args:
        label: The document to copy and modify.
        text: Text; newlines start a new line.
        font: Font spec, see :func:`load_font`.
        size_mm: Nominal glyph size in millimetres (8 dots per mm).
        x_mm: Anchor x in millimetres.
        y_mm: Anchor y in millimetres.
        anchor: One of :data:`ANCHORS`; which point of the whole text
            block sits at (x_mm, y_mm).
        align: ``left`` / ``center`` / ``right`` within the block.
        line_spacing_mm: Extra gap between lines.
        bold: Stroke width in dots (fake bold, 0 = off).
        ink: True paints black, False white.

    Returns:
        The new document.

    Raises:
        ValueError: On unknown anchor/align or bad font.
    '''
    size_dots = max(1, mm_to_dots(size_mm))
    pil_font = load_font(font, size_dots)
    lines = text.split("\n")
    ascent, descent = pil_font.getmetrics()
    line_height = ascent + descent + mm_to_dots(line_spacing_mm)
    widths = [
        int(pil_font.getbbox(line)[2]) + bold * 2 for line in lines
    ]
    block_w = max(widths)
    block_h = line_height * len(lines) - mm_to_dots(line_spacing_mm)

    dx, dy = anchor_offset(anchor, block_w, block_h)
    left = mm_to_dots(x_mm) + dx
    top = mm_to_dots(y_mm) + dy

    canvas = label.image.copy()
    draw = ImageDraw.Draw(canvas)
    fill = 0 if ink else 255
    for i, line in enumerate(lines):
        if align == "center":
            line_x = left + (block_w - widths[i]) // 2
        elif align == "right":
            line_x = left + block_w - widths[i]
        elif align == "left":
            line_x = left
        else:
            raise ValueError(f"unknown align: {align!r}")
        draw.text(
            (line_x + bold, top + i * line_height + bold),
            line,
            font=pil_font,
            fill=fill,
            stroke_width=bold,
            stroke_fill=fill,
        )
    return LabelDocument(
        image=canvas, width_dots=label.width_dots,
        height_dots=label.height_dots,
    )


def draw_barcode(
    label: LabelDocument,
    data: str,
    symbology: str = SYMBLOGY_CODE128,
    height_mm: float = 10.0,
    module_dots: int = 2,
    x_mm: float = 0.0,
    y_mm: float = 0.0,
    anchor: str = "top-left",
    quiet_zone_modules: int = DEFAULT_QUIET_MODULES,
    show_text: bool = True,
    text_mm: float = 2.5,
    ink: bool = True,
) -> LabelDocument:
    '''Draw a barcode (optionally with HRI text below).

    Args:
        label: The document to copy and modify.
        data: Payload; validation depends on the symbology.
        symbology: One of :data:`BARCODE_TYPES`.
        height_mm: Bar height in millimetres.
        module_dots: Width of one module in dots.
        x_mm: Anchor x in millimetres.
        y_mm: Anchor y in millimetres.
        anchor: One of :data:`ANCHORS` for the whole barcode block.
        quiet_zone_modules: White modules left/right of the bars.
        show_text: Print the HRI text under the bars.
        text_mm: HRI glyph size in millimetres.
        ink: True paints black, False white.

    Returns:
        The new document.

    Raises:
        ValueError: Propagated from :func:`render_barcode`.
    '''
    result = render_barcode(
        data,
        symbology=symbology,
        height_dots=mm_to_dots(height_mm),
        module_dots=module_dots,
        quiet_zone_modules=quiet_zone_modules,
    )

    block_h = result.bitmap.shape[0]
    text_block_h = 0
    if show_text:
        text_block_h = mm_to_dots(text_mm * 1.6)
        block_h += text_block_h

    dx, dy = anchor_offset(anchor, result.bitmap.shape[1], block_h)
    left = mm_to_dots(x_mm) + dx
    top = mm_to_dots(y_mm) + dy

    out = draw_bitmap(label, result.bitmap, left, top, ink=ink)
    if show_text:
        out = draw_text(
            out,
            result.hri_text,
            font="mono",
            size_mm=text_mm,
            x_mm=(left) / DOTS_PER_MM,
            y_mm=(top + result.bitmap.shape[0]) / DOTS_PER_MM,
            anchor="top-center",
            align="center",
            line_spacing_mm=0.0,
            ink=ink,
        )
    return out


def draw_qr(
    label: LabelDocument,
    data: str,
    module_dots: int = 3,
    quiet_modules: int = 4,
    ecc: str = "m",
    x_mm: float = 0.0,
    y_mm: float = 0.0,
    anchor: str = "top-left",
    ink: bool = True,
) -> LabelDocument:
    '''Draw a QR code rendered from ``data``.

    Args:
        label: The document to copy and modify.
        data: Payload (URL, text, ...).
        module_dots: Size of one QR module in dots.
        quiet_modules: White modules around the code (spec default 4).
        ecc: Error correction level ``l`` / ``m`` / ``q`` / ``h``.
        x_mm: Anchor x in millimetres.
        y_mm: Anchor y in millimetres.
        anchor: One of :data:`ANCHORS`.
        ink: True paints black, False white.

    Returns:
        The new document.
    '''
    import segno

    qr = segno.make(data, error=ecc)
    matrix = np.asarray(qr.matrix, dtype=np.bool_)
    side = matrix.shape[0] + 2 * quiet_modules
    padded = np.zeros((side, side), dtype=np.bool_)
    padded[
        quiet_modules : quiet_modules + matrix.shape[0],
        quiet_modules : quiet_modules + matrix.shape[0],
    ] = matrix
    bitmap = np.repeat(
        np.repeat(padded, module_dots, axis=0), module_dots, axis=1
    )

    dx, dy = anchor_offset(anchor, bitmap.shape[1], bitmap.shape[0])
    return draw_bitmap(
        label,
        bitmap,
        mm_to_dots(x_mm) + dx,
        mm_to_dots(y_mm) + dy,
        ink=ink,
    )


def draw_rect(
    label: LabelDocument,
    x_mm: float,
    y_mm: float,
    width_mm: float,
    height_mm: float,
    thickness_dots: int = 2,
    filled: bool = False,
    ink: bool = True,
) -> LabelDocument:
    '''Draw a rectangle outline or a filled rectangle.

    Args:
        label: The document to copy and modify.
        x_mm: Left edge in millimetres.
        y_mm: Top edge in millimetres.
        width_mm: Width in millimetres.
        height_mm: Height in millimetres.
        thickness_dots: Outline thickness in dots (0 = hairline).
        filled: Draw a solid rectangle instead of an outline.
        ink: True paints black, False white.

    Returns:
        The new document.
    '''
    canvas = label.image.copy()
    draw = ImageDraw.Draw(canvas)
    box = (
        mm_to_dots(x_mm),
        mm_to_dots(y_mm),
        mm_to_dots(x_mm + width_mm),
        mm_to_dots(y_mm + height_mm),
    )
    fill = (0 if ink else 255) if filled else None
    outline = 0 if ink else 255
    draw.rectangle(
        box, fill=fill, outline=outline, width=max(0, thickness_dots)
    )
    return LabelDocument(
        image=canvas, width_dots=label.width_dots,
        height_dots=label.height_dots,
    )


def prepare_image_block(
    gray: np.ndarray,
    box_w: int,
    box_h: int,
    fit: str = FIT_CONTAIN,
    dither_method: str = DITHER_FLOYD_STEINBERG,
    brightness: float = 0.0,
    contrast: float = 0.0,
    gamma: float = 1.0,
    invert: bool = False,
) -> np.ndarray:
    '''Scale a grayscale image into a box and dither it to 1 bit.

    Args:
        gray: Float32 array (H, W) in [0, 255].
        box_w: Target width in dots.
        box_h: Target height in dots.
        fit: One of :data:`FIT_MODES`.
        dither_method: One of :data:`DITHER_METHODS`.
        brightness: Added before dithering (gray levels).
        contrast: -1..1, see :func:`adjust_tone`.
        gamma: Tone gamma, see :func:`adjust_tone`.
        invert: Swap black and white before dithering.

    Returns:
        Bool bitmap sized exactly (box_h, box_w); True = ink.

    Raises:
        ValueError: On unknown fit or dither method.
    '''
    if fit not in FIT_MODES:
        raise ValueError(f"unknown fit mode: {fit!r}")
    src = Image.fromarray(
        np.clip(gray, 0.0, 255.0).astype(np.uint8), mode="L"
    )

    if fit == FIT_STRETCH:
        resized = src.resize((box_w, box_h), Image.Resampling.LANCZOS)
    elif fit == FIT_CONTAIN:
        resized = src.copy()
        resized.thumbnail((box_w, box_h), Image.Resampling.LANCZOS)
    else:  # cover
        from PIL import ImageOps

        resized = ImageOps.fit(
            src, (box_w, box_h), method=Image.Resampling.LANCZOS
        )

    block = Image.new("L", (box_w, box_h), 255)
    block.paste(
        resized, ((box_w - resized.width) // 2, (box_h - resized.height) // 2)
    )
    toned = adjust_tone(
        np.asarray(block, dtype=np.float32),
        brightness=brightness,
        contrast=contrast,
        gamma=gamma,
        invert=invert,
    )
    return dither(toned, dither_method)
