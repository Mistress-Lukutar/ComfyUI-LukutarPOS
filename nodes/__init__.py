'''
File:   __init__.py
Brief:  Node registry of the POS label pack.
Author: Mistress-Lukutar
Date:   2026-09-03
Version: v0.1.0
'''

from __future__ import annotations

from .label_elements import (
    LabelBarcodeNode,
    LabelCanvasNode,
    LabelImageNode,
    LabelQRNode,
    LabelRectNode,
    LabelTextNode,
)
from .label_output import (
    LabelPreviewNode,
    PrintLabelNode,
    SaveLabelStreamNode,
)

NODE_CLASS_MAPPINGS: dict[str, type] = {
    "LabelCanvas": LabelCanvasNode,
    "LabelImage": LabelImageNode,
    "LabelText": LabelTextNode,
    "LabelBarcode": LabelBarcodeNode,
    "LabelQR": LabelQRNode,
    "LabelRect": LabelRectNode,
    "LabelPreview": LabelPreviewNode,
    "PrintLabel": PrintLabelNode,
    "SaveLabelStream": SaveLabelStreamNode,
}

NODE_DISPLAY_NAME_MAPPINGS: dict[str, str] = {
    "LabelCanvas": "Label Canvas (Lukutar)",
    "LabelImage": "Label Image (Lukutar)",
    "LabelText": "Label Text (Lukutar)",
    "LabelBarcode": "Label Barcode (Lukutar)",
    "LabelQR": "Label QR Code (Lukutar)",
    "LabelRect": "Label Line / Frame (Lukutar)",
    "LabelPreview": "Label Preview (Lukutar)",
    "PrintLabel": "Print Label / Windows RAW (Lukutar)",
    "SaveLabelStream": "Save Label Stream / ESC-POS (Lukutar)",
}

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
]
