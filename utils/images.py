'''
File:   images.py
Brief:  Conversion between ComfyUI IMAGE tensors and label grayframes.
Author: Mistress-Lukutar
Date:   2026-09-03
Version: v0.1.0

torch is imported lazily inside the functions: the whole pack (this
module included) must import on any plain python so unit tests and
ComfyUI's loader both work without the runtime.
'''

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from ..core.label import LabelDocument


def tensor_frame_to_gray(image: Any, frame: int = 0) -> np.ndarray:
    '''Extract one frame of a ComfyUI IMAGE tensor as grayscale.

    Args:
        image: Tensor of shape (B, H, W, 3), float in [0, 1], RGB; may
            live on any device.
        frame: Batch index to extract.

    Returns:
        Float32 array (H, W) in [0, 255], Rec.601 luminance.
    '''

    tensor = image.detach().cpu()[frame].clamp(0.0, 1.0)
    rgb = tensor.numpy() * 255.0
    return (
        rgb[..., 0] * 0.299
        + rgb[..., 1] * 0.587
        + rgb[..., 2] * 0.114
    ).astype(np.float32)


def gray_to_tensor(gray: np.ndarray) -> Any:
    '''Expand a grayscale frame into a ComfyUI IMAGE tensor.

    Args:
        gray: Array (H, W), any numeric range; clipped to [0, 255].

    Returns:
        Tensor of shape (1, H, W, 3), float32 in [0, 1], RGB.
    '''
    import torch

    clipped = np.clip(gray, 0.0, 255.0).astype(np.float32)
    rgbhwc = np.repeat(clipped[..., np.newaxis], 3, axis=-1) / 255.0
    return torch.from_numpy(rgbhwc[np.newaxis, ...])


def label_to_tensor(label: LabelDocument) -> Any:
    '''A label document as a preview IMAGE tensor (1, H, W, 3).

    Args:
        label: The document to convert.

    Returns:
        Tensor of shape (1, H, W, 3), float32 in [0, 1], RGB.
    '''
    return gray_to_tensor(label.to_gray())
