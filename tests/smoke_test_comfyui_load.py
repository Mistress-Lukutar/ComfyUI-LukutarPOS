'''
File:   smoke_test_comfyui_load.py
Brief:  Simulates ComfyUI custom node loading without launching the
        server, then composes a label end to end.
Author: Mistress-Lukutar
Date:   2026-09-03
Version: v0.1.0

Run with ComfyUI's own python (no server launch required):

    C:/Ai/ComfyUI_windows_portable/python_embeded/python.exe \
        tests/smoke_test_comfyui_load.py
'''

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

import numpy as np
import torch

PACK_ROOT = Path(__file__).resolve().parent.parent

EXPECTED_NODES = (
    "LabelCanvas",
    "LabelImage",
    "LabelText",
    "LabelBarcode",
    "LabelQR",
    "LabelRect",
    "LabelPreview",
    "PrintLabel",
    "SaveLabelStream",
)


def load_pack() -> object:
    '''Import the pack exactly the way ComfyUI's load_custom_node does.'''
    module_name = "custom_nodes.ComfyUI-LukutarPOS"
    spec = importlib.util.spec_from_file_location(
        module_name,
        PACK_ROOT / "__init__.py",
        submodule_search_locations=[str(PACK_ROOT)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to create import spec for the pack")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _synthetic_image() -> torch.Tensor:
    '''A gradient IMAGE batch (2, 64, 64, 3) in [0, 1].'''
    axis = np.linspace(0.0, 255.0, 64, dtype=np.float32)
    grid = axis[np.newaxis, :] + axis[:, np.newaxis]
    frame = np.stack(
        [np.clip(grid, 0, 255), np.clip(255 - grid, 0, 255), grid * 0.5],
        axis=-1,
    )
    tensor = torch.from_numpy((frame / 255.0).astype(np.float32))[None]
    return tensor.repeat(2, 1, 1, 1)


def main() -> None:
    pack = load_pack()
    mappings = getattr(pack, "NODE_CLASS_MAPPINGS", None)
    assert mappings, "NODE_CLASS_MAPPINGS missing"
    for key in EXPECTED_NODES:
        assert key in mappings, f"{key} not registered"
        assert key in pack.NODE_DISPLAY_NAME_MAPPINGS  # type: ignore[attr-defined]

    # Element chain: canvas -> frame -> image -> text -> barcode -> QR.
    (label,) = mappings["LabelCanvas"]().create(
        "60mm roll / 40mm label (448x320)"
    )
    assert (label.width_dots, label.height_dots) == (448, 320)

    (label,) = mappings["LabelRect"]().draw(
        label, 1.0, 1.0, 54.0, 38.0, 2, False, "black"
    )

    (label,) = mappings["LabelImage"]().draw(
        label,
        _synthetic_image(),
        x_mm=2.0,
        y_mm=2.0,
        width_mm=30.0,
        height_mm=20.0,
        anchor="top-left",
        fit="contain",
        dither="floyd-steinberg",
        brightness=0.0,
        contrast=0.0,
        gamma=1.0,
        invert=False,
        frame=1,  # second frame of the batch
    )

    (label,) = mappings["LabelText"]().draw(
        label,
        text="LukutaR\nЭтикетка 60x40",
        font="bold",
        size_mm=3.0,
        x_mm=34.0,
        y_mm=3.0,
        anchor="top-left",
        align="left",
        line_spacing_mm=0.5,
        bold=0,
        ink="black",
    )

    (label,) = mappings["LabelBarcode"]().draw(
        label,
        data="4006381333931",
        symbology="EAN-13",
        height_mm=8.0,
        module_dots=2,
        x_mm=3.0,
        y_mm=27.0,
        anchor="top-left",
        quiet_zone_modules=10,
        show_text=True,
        text_mm=2.0,
        ink="black",
    )

    (label,) = mappings["LabelQR"]().draw(
        label,
        data="https://example.com/label",
        module_dots=2,
        quiet_modules=4,
        ecc="m",
        x_mm=44.0,
        y_mm=20.0,
        anchor="center",
        ink="black",
    )

    bitmap = label.to_bitmap()
    assert bitmap.any(), "composed label must contain ink"
    assert not bitmap.all(), "composed label must contain paper"

    # Preview converts to a valid IMAGE tensor.
    (preview,) = mappings["LabelPreview"]().preview(label)
    assert preview.dtype == torch.float32
    assert tuple(preview.shape) == (1, 320, 448, 3)
    assert float(preview.min()) >= 0.0 and float(preview.max()) <= 1.0

    # Save node writes the exact ESC/POS payload to disk.
    save_node = mappings["SaveLabelStream"]()
    output_module = sys.modules[
        "custom_nodes.ComfyUI-LukutarPOS.nodes.label_output"
    ]
    with tempfile.TemporaryDirectory() as tmp:
        real_directory = output_module._output_directory
        output_module._output_directory = lambda: tmp  # type: ignore[assignment]
        try:
            result = save_node.save(
                label, "smoke", "high quality (low speed)", "feed", 1
            )
        finally:
            output_module._output_directory = real_directory  # type: ignore[assignment]
        path = Path(result["result"][0])
        assert path.exists() and path.suffix == ".bin"
        stream = path.read_bytes()
        # ESC @ + ESC x 2 + ESC FD + nL nH + raster + ESC FA + args + LF
        num_words = 320 * 28
        assert len(stream) == 17 + num_words * 2
        assert stream[:2] == b"\x1b\x40"
        assert stream[2:5] == b"\x1b\x78\x02"

    # The print payload is byte-identical to what was saved (the RAW
    # transport itself is deliberately not exercised here).
    expected = label.to_stream(
        quality="high quality (low speed)", finish="feed", copies=1
    )
    assert expected == stream

    print("SMOKE TEST PASSED: nodes load and compose a printable label")


if __name__ == "__main__":
    main()
