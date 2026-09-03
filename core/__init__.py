'''
File:   __init__.py
Brief:  Core engines of the POS label pack (torch-free, ComfyUI-free).
Author: Mistress-Lukutar
Date:   2026-09-03
Version: v0.1.0
'''

from __future__ import annotations

from .barcode import (
    BARCODE_TYPES,
    SYMBLOGY_CODABAR,
    SYMBLOGY_CODE39,
    SYMBLOGY_CODE128,
    SYMBLOGY_EAN8,
    SYMBLOGY_EAN13,
    SYMBLOGY_ITF,
    SYMBLOGY_UPC_A,
    render_barcode,
)
from .dithering import (
    DITHER_FLOYD_STEINBERG,
    DITHER_METHODS,
    DITHER_ORDERED_2,
    DITHER_ORDERED_4,
    DITHER_ORDERED_8,
    DITHER_THRESHOLD,
    adjust_tone,
    dither,
)
from .escpos import (
    FINISH_FEED,
    FINISH_MODES,
    FINISH_NONE,
    FINISH_PARTIAL_CUT,
    FINISH_TOTAL_CUT,
    MODEL_TPTCM60,
    MODEL_TPTCM112,
    PRINT_MODELS,
    QUALITY_DRAFT,
    QUALITY_HIGH,
    QUALITY_MODES,
    QUALITY_NORMAL,
    build_label_stream,
    pack_graphic_page,
)
from .label import (
    ANCHORS,
    DOTS_PER_MM,
    FIT_CONTAIN,
    FIT_COVER,
    FIT_MODES,
    FIT_STRETCH,
    LABEL_CUSTOM,
    LABEL_SIZES,
    LABEL_60x40,
    LabelDocument,
    create_label,
    draw_barcode,
    draw_bitmap,
    draw_qr,
    draw_rect,
    draw_text,
    load_font,
    mm_to_dots,
    prepare_image_block,
)
from .transport import save_stream_file, send_raw_windows

__all__ = [
    # escpos protocol
    "FINISH_FEED",
    "FINISH_MODES",
    "FINISH_NONE",
    "FINISH_PARTIAL_CUT",
    "FINISH_TOTAL_CUT",
    "MODEL_TPTCM60",
    "MODEL_TPTCM112",
    "PRINT_MODELS",
    "QUALITY_DRAFT",
    "QUALITY_HIGH",
    "QUALITY_MODES",
    "QUALITY_NORMAL",
    "build_label_stream",
    "pack_graphic_page",
    # dithering
    "DITHER_FLOYD_STEINBERG",
    "DITHER_METHODS",
    "DITHER_ORDERED_2",
    "DITHER_ORDERED_4",
    "DITHER_ORDERED_8",
    "DITHER_THRESHOLD",
    "adjust_tone",
    "dither",
    # barcode
    "BARCODE_TYPES",
    "SYMBLOGY_CODE128",
    "SYMBLOGY_CODABAR",
    "SYMBLOGY_CODE39",
    "SYMBLOGY_EAN13",
    "SYMBLOGY_EAN8",
    "SYMBLOGY_ITF",
    "SYMBLOGY_UPC_A",
    "render_barcode",
    # label compositor
    "ANCHORS",
    "DOTS_PER_MM",
    "FIT_CONTAIN",
    "FIT_COVER",
    "FIT_MODES",
    "FIT_STRETCH",
    "LABEL_60x40",
    "LABEL_CUSTOM",
    "LABEL_SIZES",
    "LabelDocument",
    "create_label",
    "draw_barcode",
    "draw_bitmap",
    "draw_qr",
    "draw_rect",
    "draw_text",
    "load_font",
    "mm_to_dots",
    "prepare_image_block",
    # transport
    "save_stream_file",
    "send_raw_windows",
]
