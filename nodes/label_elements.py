'''
File:   label_elements.py
Brief:  ComfyUI nodes that build the label: canvas, image, text,
        barcode, QR code, rectangle.
Author: Mistress-Lukutar
Date:   2026-09-03
Version: v0.1.0

Every element node takes a LABEL (and its payload) and returns a new
LABEL — a pass-through chain, so a label is assembled by wiring
Canvas -> Image -> Text -> Barcode -> ... in draw order. The nodes are
torch-free: only the IMAGE input of Label Image is a tensor, and it is
touched exclusively inside the conversion helper.
'''

from __future__ import annotations

import logging
from typing import Any

from ..core import DITHER_METHODS
from ..core import label as core
from ..utils.images import tensor_frame_to_gray

logger = logging.getLogger(__name__)

#: Ink colours offered by the element nodes.
INK_BLACK = "black"
#: White ink (paint on dark areas / erase).
INK_WHITE = "white"
#: Selectable ink colours.
INK_COLORS: tuple[str, ...] = (INK_BLACK, INK_WHITE)

#: Text alignment within its block.
ALIGN_LEFT = "left"
#: Center the text lines within the block.
ALIGN_CENTER = "center"
#: Right-align the text lines within the block.
ALIGN_RIGHT = "right"
#: Selectable text alignments.
TEXT_ALIGNS: tuple[str, ...] = (ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT)

#: QR error correction levels accepted by segno.
QR_ECC_LEVELS: tuple[str, ...] = ("l", "m", "q", "h")


def _ink(value: str) -> bool:
    '''Map an ink combo value to the compositor's bool ink.

    Args:
        value: One of :data:`INK_COLORS`.

    Returns:
        True for black ink, False for white.
    '''
    return value == INK_BLACK


class LabelCanvasNode:
    '''Start a label — the blank page every element is drawn on.

    Picks a stock preset (60 mm or 112 mm roll, common feed lengths)
    or a custom size in print dots. The canvas is 1-bit at 203 DPI
    (8 dots/mm); 60 mm stock has a 448-dot (56 mm) printable width.
    '''

    CATEGORY = "Lukutar/POS"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, tuple]]:
        return {
            "required": {
                "size": (
                    list(core.LABEL_SIZES.keys()),
                    {
                        "default": core.LABEL_60x40,
                        "tooltip": (
                            "Label stock preset; 60mm rolls print 448"
                            " dots (56mm) wide"
                        ),
                    },
                ),
            },
            "optional": {
                "width_dots": (
                    "INT",
                    {
                        "default": 448,
                        "min": 1,
                        "max": 832,
                        "tooltip": "Canvas width in dots (size=custom)",
                    },
                ),
                "height_dots": (
                    "INT",
                    {
                        "default": 320,
                        "min": 1,
                        "max": 585,
                        "tooltip": "Canvas height in dotlines (size=custom)",
                    },
                ),
                "dark_background": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Start black for white-ink designs",
                    },
                ),
            },
        }

    RETURN_TYPES = ("LABEL",)
    RETURN_NAMES = ("label",)
    FUNCTION = "create"

    def create(
        self,
        size: str,
        width_dots: int = 448,
        height_dots: int = 320,
        dark_background: bool = False,
    ) -> tuple[core.LabelDocument]:
        '''Create the canvas for the chosen preset.

        Args:
            size: Preset name; ``custom`` uses the dot widgets.
            width_dots: Width for ``custom``.
            height_dots: Height for ``custom``.
            dark_background: Black canvas instead of white.

        Returns:
            One-element tuple with the new document.
        '''
        preset = core.LABEL_SIZES.get(size)
        if preset is not None:
            width_dots, height_dots = preset
        label = core.create_label(width_dots, height_dots, dark_background)
        logger.debug(
            "canvas %dx%d dots (%.1f x %.1f mm)",
            width_dots,
            height_dots,
            width_dots / core.DOTS_PER_MM,
            height_dots / core.DOTS_PER_MM,
        )
        return (label,)


class LabelImageNode:
    '''Place a generated image on the label, dithered to 1 bit.

    Takes one frame of a ComfyUI IMAGE, scales it into the target
    millimetre box (contain / cover / stretch), applies tone controls
    and dithering (Floyd-Steinberg for photos, Bayer for line art,
    threshold for already-black artwork), then pastes the result.
    '''

    CATEGORY = "Lukutar/POS"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, tuple]]:
        return {
            "required": {
                "label": (
                    "LABEL",
                    {"tooltip": "Label canvas to draw on (pass-through)"},
                ),
                "image": (
                    "IMAGE",
                    {"tooltip": "Image batch; one frame is placed"},
                ),
                "x_mm": (
                    "FLOAT",
                    {
                        "default": 0.0,
                        "tooltip": "Box position x (anchor point), mm",
                    },
                ),
                "y_mm": (
                    "FLOAT",
                    {
                        "default": 0.0,
                        "tooltip": "Box position y (anchor point), mm",
                    },
                ),
                "width_mm": (
                    "FLOAT",
                    {
                        "default": 56.0,
                        "min": 0.5,
                        "tooltip": "Box width in mm (8 dots per mm)",
                    },
                ),
                "height_mm": (
                    "FLOAT",
                    {
                        "default": 25.0,
                        "min": 0.5,
                        "tooltip": "Box height in mm",
                    },
                ),
                "anchor": (
                    list(core.ANCHORS),
                    {
                        "default": "top-left",
                        "tooltip": "Which corner of the image box (x, y) is",
                    },
                ),
                "fit": (
                    list(core.FIT_MODES),
                    {
                        "default": core.FIT_CONTAIN,
                        "tooltip": (
                            "contain: whole image inside the box; cover:"
                            " fill and crop; stretch: distort to fit"
                        ),
                    },
                ),
                "dither": (
                    list(DITHER_METHODS),
                    {
                        "default": core.DITHER_FLOYD_STEINBERG,
                        "tooltip": (
                            "floyd-steinberg for photos; ordered (Bayer)"
                            " for crisp lines; threshold for 1-bit art"
                        ),
                    },
                ),
                "brightness": (
                    "FLOAT",
                    {
                        "default": 0.0,
                        "min": -255.0,
                        "max": 255.0,
                        "tooltip": "Gray levels added before dithering",
                    },
                ),
                "contrast": (
                    "FLOAT",
                    {
                        "default": 0.0,
                        "min": -1.0,
                        "max": 1.0,
                        "tooltip": "Push away from mid gray (>0 = punchier)",
                    },
                ),
                "gamma": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.1,
                        "max": 5.0,
                        "tooltip": ">1 brightens, <1 darkens",
                    },
                ),
                "invert": (
                    "BOOLEAN",
                    {"default": False, "tooltip": "Swap black and white"},
                ),
                "frame": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "tooltip": "Batch index of the frame to print",
                    },
                ),
            },
        }

    RETURN_TYPES = ("LABEL",)
    RETURN_NAMES = ("label",)
    FUNCTION = "draw"

    def draw(
        self,
        label: core.LabelDocument,
        image: Any,
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float,
        anchor: str,
        fit: str,
        dither: str,
        brightness: float,
        contrast: float,
        gamma: float,
        invert: bool,
        frame: int,
    ) -> tuple[core.LabelDocument]:
        '''Dither one frame and paste it into the box.

        Args:
            label: Canvas so far.
            image: ComfyUI IMAGE tensor.
            x_mm: Box anchor x in mm.
            y_mm: Box anchor y in mm.
            width_mm: Box width in mm.
            height_mm: Box height in mm.
            anchor: Which point of the box (x, y) refers to.
            fit: contain / cover / stretch.
            dither: Dithering method name.
            brightness: Tone control, gray levels.
            contrast: Tone control, -1..1.
            gamma: Tone control.
            invert: Swap black and white before dithering.
            frame: Batch index to take.

        Returns:
            One-element tuple with the updated document.
        '''
        gray = tensor_frame_to_gray(image, frame)
        box_w = core.mm_to_dots(width_mm)
        box_h = core.mm_to_dots(height_mm)
        bitmap = core.prepare_image_block(
            gray,
            box_w,
            box_h,
            fit=fit,
            dither_method=dither,
            brightness=brightness,
            contrast=contrast,
            gamma=gamma,
            invert=invert,
        )
        dx, dy = core.anchor_offset(anchor, box_w, box_h)
        return (core.draw_bitmap(
            label, bitmap, core.mm_to_dots(x_mm) + dx,
            core.mm_to_dots(y_mm) + dy, ink=True,
        ),)


class LabelTextNode:
    '''Draw text on the label with any TTF font.

    The default bundled font (DejaVu Sans) covers Latin and Cyrillic;
    ``bold`` and ``mono`` name the other bundled faces, and an absolute
    path to any .ttf/.otf works too. Raster text ignores the printer's
    code tables — whatever glyphs the font has will print.
    '''

    CATEGORY = "Lukutar/POS"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, tuple]]:
        return {
            "required": {
                "label": (
                    "LABEL",
                    {"tooltip": "Label canvas to draw on (pass-through)"},
                ),
                "text": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "tooltip": (
                            "Text; \\n starts a new line; connect a"
                            " STRING to print dynamic values"
                        ),
                    },
                ),
                "font": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": (
                            "'', 'bold', 'mono' or a path to a .ttf file"
                        ),
                    },
                ),
                "size_mm": (
                    "FLOAT",
                    {
                        "default": 3.0,
                        "min": 0.5,
                        "tooltip": "Glyph height in mm (8 dots per mm)",
                    },
                ),
                "x_mm": (
                    "FLOAT",
                    {"default": 2.0, "tooltip": "Anchor x in mm"},
                ),
                "y_mm": (
                    "FLOAT",
                    {"default": 2.0, "tooltip": "Anchor y in mm"},
                ),
                "anchor": (
                    list(core.ANCHORS),
                    {
                        "default": "top-left",
                        "tooltip": "Which point of the text block (x, y) is",
                    },
                ),
                "align": (
                    list(TEXT_ALIGNS),
                    {
                        "default": ALIGN_LEFT,
                        "tooltip": "Line alignment inside the text block",
                    },
                ),
                "line_spacing_mm": (
                    "FLOAT",
                    {
                        "default": 0.5,
                        "min": 0.0,
                        "tooltip": "Extra gap between lines in mm",
                    },
                ),
                "bold": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 8,
                        "tooltip": "Stroke width in dots (fake bold)",
                    },
                ),
                "ink": (
                    list(INK_COLORS),
                    {"default": INK_BLACK, "tooltip": "Ink colour"},
                ),
            },
        }

    RETURN_TYPES = ("LABEL",)
    RETURN_NAMES = ("label",)
    FUNCTION = "draw"

    def draw(
        self,
        label: core.LabelDocument,
        text: str,
        font: str,
        size_mm: float,
        x_mm: float,
        y_mm: float,
        anchor: str,
        align: str,
        line_spacing_mm: float,
        bold: int,
        ink: str,
    ) -> tuple[core.LabelDocument]:
        '''Rasterize the text and draw it.

        Args:
            label: Canvas so far.
            text: Text with optional newlines.
            font: Font spec (see :func:`core.load_font`).
            size_mm: Glyph height in mm.
            x_mm: Anchor x in mm.
            y_mm: Anchor y in mm.
            anchor: Anchor point of the whole text block.
            align: left / center / right inside the block.
            line_spacing_mm: Extra gap between lines.
            bold: Stroke width in dots.
            ink: black / white.

        Returns:
            One-element tuple with the updated document.
        '''
        return (
            core.draw_text(
                label,
                text,
                font=font,
                size_mm=size_mm,
                x_mm=x_mm,
                y_mm=y_mm,
                anchor=anchor,
                align=align,
                line_spacing_mm=line_spacing_mm,
                bold=bold,
                ink=_ink(ink),
            ),
        )


class LabelBarcodeNode:
    '''Draw a 1-D barcode (CODE128, EAN, UPC, CODE39, ITF, CODABAR).

    Rendered into the label bitmap rather than sent as the native
    ``GS k`` command, so the preview matches the print exactly.
    Checksums (EAN/UPC/CODE128) are computed automatically.
    '''

    CATEGORY = "Lukutar/POS"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, tuple]]:
        from ..core import BARCODE_TYPES, SYMBLOGY_CODE128

        return {
            "required": {
                "label": (
                    "LABEL",
                    {"tooltip": "Label canvas to draw on (pass-through)"},
                ),
                "data": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": (
                            "Payload; digits for EAN/UPC/ITF, digits and"
                            " A-D wrapper for CODABAR (e.g. A1234B)"
                        ),
                    },
                ),
                "symbology": (
                    list(BARCODE_TYPES),
                    {"default": SYMBLOGY_CODE128},
                ),
                "height_mm": (
                    "FLOAT",
                    {
                        "default": 10.0,
                        "min": 2.0,
                        "tooltip": "Bar height in mm",
                    },
                ),
                "module_dots": (
                    "INT",
                    {
                        "default": 2,
                        "min": 1,
                        "max": 4,
                        "tooltip": (
                            "Width of the narrowest bar in dots; 2 scans"
                            " reliably at 203 DPI"
                        ),
                    },
                ),
                "x_mm": (
                    "FLOAT",
                    {"default": 3.0, "tooltip": "Anchor x in mm"},
                ),
                "y_mm": (
                    "FLOAT",
                    {"default": 20.0, "tooltip": "Anchor y in mm"},
                ),
                "anchor": (
                    list(core.ANCHORS),
                    {"default": "top-left"},
                ),
                "quiet_zone_modules": (
                    "INT",
                    {
                        "default": 10,
                        "min": 0,
                        "tooltip": "White modules left/right of the bars",
                    },
                ),
                "show_text": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Print the data under the bars (HRI)",
                    },
                ),
                "text_mm": (
                    "FLOAT",
                    {
                        "default": 2.5,
                        "min": 1.0,
                        "tooltip": "HRI glyph height in mm",
                    },
                ),
                "ink": (
                    list(INK_COLORS),
                    {"default": INK_BLACK},
                ),
            },
        }

    RETURN_TYPES = ("LABEL",)
    RETURN_NAMES = ("label",)
    FUNCTION = "draw"

    def draw(
        self,
        label: core.LabelDocument,
        data: str,
        symbology: str,
        height_mm: float,
        module_dots: int,
        x_mm: float,
        y_mm: float,
        anchor: str,
        quiet_zone_modules: int,
        show_text: bool,
        text_mm: float,
        ink: str,
    ) -> tuple[core.LabelDocument]:
        '''Render the barcode and draw it.

        Args:
            label: Canvas so far.
            data: Payload for the chosen symbology.
            symbology: One of :data:`core.BARCODE_TYPES`.
            height_mm: Bar height in mm.
            module_dots: Narrow bar width in dots.
            x_mm: Anchor x in mm.
            y_mm: Anchor y in mm.
            anchor: Anchor point of the barcode block.
            quiet_zone_modules: Quiet zone width in modules.
            show_text: Draw the HRI text under the bars.
            text_mm: HRI glyph height in mm.
            ink: black / white.

        Returns:
            One-element tuple with the updated document.
        '''
        return (
            core.draw_barcode(
                label,
                data,
                symbology=symbology,
                height_mm=height_mm,
                module_dots=module_dots,
                x_mm=x_mm,
                y_mm=y_mm,
                anchor=anchor,
                quiet_zone_modules=quiet_zone_modules,
                show_text=show_text,
                text_mm=text_mm,
                ink=_ink(ink),
            ),
        )


class LabelQRNode:
    '''Draw a QR code — the printer has no native QR, so it is rasterized.

    Size in mm follows from ``module_dots``: a version-1 code (21
    modules + quiet zone) at 3 dots/module prints ~11 mm wide.
    '''

    CATEGORY = "Lukutar/POS"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, tuple]]:
        return {
            "required": {
                "label": (
                    "LABEL",
                    {"tooltip": "Label canvas to draw on (pass-through)"},
                ),
                "data": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Payload: URL, text, serial, ...",
                    },
                ),
                "module_dots": (
                    "INT",
                    {
                        "default": 3,
                        "min": 1,
                        "max": 8,
                        "tooltip": "One QR module in print dots",
                    },
                ),
                "quiet_modules": (
                    "INT",
                    {
                        "default": 4,
                        "min": 0,
                        "tooltip": "White modules around the code",
                    },
                ),
                "ecc": (
                    list(QR_ECC_LEVELS),
                    {
                        "default": "m",
                        "tooltip": (
                            "Error correction: l=7% m=15% q=25% h=30%"
                        ),
                    },
                ),
                "x_mm": (
                    "FLOAT",
                    {"default": 30.0, "tooltip": "Anchor x in mm"},
                ),
                "y_mm": (
                    "FLOAT",
                    {"default": 4.0, "tooltip": "Anchor y in mm"},
                ),
                "anchor": (
                    list(core.ANCHORS),
                    {"default": "top-left"},
                ),
                "ink": (
                    list(INK_COLORS),
                    {"default": INK_BLACK},
                ),
            },
        }

    RETURN_TYPES = ("LABEL",)
    RETURN_NAMES = ("label",)
    FUNCTION = "draw"

    def draw(
        self,
        label: core.LabelDocument,
        data: str,
        module_dots: int,
        quiet_modules: int,
        ecc: str,
        x_mm: float,
        y_mm: float,
        anchor: str,
        ink: str,
    ) -> tuple[core.LabelDocument]:
        '''Render the QR code and draw it.

        Args:
            label: Canvas so far.
            data: QR payload.
            module_dots: Module size in dots.
            quiet_modules: Quiet zone width in modules.
            ecc: Error correction level l/m/q/h.
            x_mm: Anchor x in mm.
            y_mm: Anchor y in mm.
            anchor: Anchor point of the QR block.
            ink: black / white.

        Returns:
            One-element tuple with the updated document.
        '''
        return (
            core.draw_qr(
                label,
                data,
                module_dots=module_dots,
                quiet_modules=quiet_modules,
                ecc=ecc,
                x_mm=x_mm,
                y_mm=y_mm,
                anchor=anchor,
                ink=_ink(ink),
            ),
        )


class LabelRectNode:
    '''Draw a frame, a filled block or a thick separator line.

    A rectangle with height 1 mm and filled=True is a horizontal rule;
    outline rectangles make the classic label border.
    '''

    CATEGORY = "Lukutar/POS"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, tuple]]:
        return {
            "required": {
                "label": (
                    "LABEL",
                    {"tooltip": "Label canvas to draw on (pass-through)"},
                ),
                "x_mm": (
                    "FLOAT",
                    {"default": 1.0, "tooltip": "Left edge in mm"},
                ),
                "y_mm": (
                    "FLOAT",
                    {"default": 1.0, "tooltip": "Top edge in mm"},
                ),
                "width_mm": (
                    "FLOAT",
                    {"default": 54.0, "tooltip": "Width in mm"},
                ),
                "height_mm": (
                    "FLOAT",
                    {"default": 38.0, "tooltip": "Height in mm"},
                ),
                "thickness_dots": (
                    "INT",
                    {
                        "default": 2,
                        "min": 0,
                        "max": 16,
                        "tooltip": "Outline thickness in dots",
                    },
                ),
                "filled": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Solid block instead of an outline",
                    },
                ),
                "ink": (
                    list(INK_COLORS),
                    {"default": INK_BLACK},
                ),
            },
        }

    RETURN_TYPES = ("LABEL",)
    RETURN_NAMES = ("label",)
    FUNCTION = "draw"

    def draw(
        self,
        label: core.LabelDocument,
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float,
        thickness_dots: int,
        filled: bool,
        ink: str,
    ) -> tuple[core.LabelDocument]:
        '''Draw the rectangle.

        Args:
            label: Canvas so far.
            x_mm: Left edge in mm.
            y_mm: Top edge in mm.
            width_mm: Width in mm.
            height_mm: Height in mm.
            thickness_dots: Outline thickness in dots.
            filled: Solid rectangle instead of outline.
            ink: black / white.

        Returns:
            One-element tuple with the updated document.
        '''
        return (
            core.draw_rect(
                label,
                x_mm,
                y_mm,
                width_mm,
                height_mm,
                thickness_dots=thickness_dots,
                filled=filled,
                ink=_ink(ink),
            ),
        )
