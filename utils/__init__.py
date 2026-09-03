'''
File:   __init__.py
Brief:  Tensor/label conversion helpers for the POS label pack.
Author: Mistress-Lukutar
Date:   2026-09-03
Version: v0.1.0
'''

from __future__ import annotations

from .images import label_to_tensor, tensor_frame_to_gray

__all__ = ["label_to_tensor", "tensor_frame_to_gray"]
