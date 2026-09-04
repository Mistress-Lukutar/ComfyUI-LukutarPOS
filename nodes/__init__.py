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
    LabelImageRotateNode,
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
    "LabelImageRotate": LabelImageRotateNode,
    "LabelText": LabelTextNode,
    "LabelBarcode": LabelBarcodeNode,
    "LabelQR": LabelQRNode,
    "LabelRect": LabelRectNode,
    "LabelPreview": LabelPreviewNode,
    "PrintLabel": PrintLabelNode,
    "SaveLabelStream": SaveLabelStreamNode,
}

NODE_DISPLAY_NAME_MAPPINGS: dict[str, str] = {
    "LabelCanvas": "Label Canvas",
    "LabelImage": "Label Image",
    "LabelImageRotate": "Label Image Rotate",
    "LabelText": "Label Text",
    "LabelBarcode": "Label Barcode",
    "LabelQR": "Label QR Code",
    "LabelRect": "Label Line / Frame",
    "LabelPreview": "Label Preview",
    "PrintLabel": "Print Label / Windows RAW",
    "SaveLabelStream": "Save Label Stream / ESC-POS",
}

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
]
