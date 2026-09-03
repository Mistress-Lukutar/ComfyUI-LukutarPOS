'''
File:   label_output.py
Brief:  ComfyUI output nodes: preview, Windows RAW print, stream save.
Author: Mistress-Lukutar
Date:   2026-09-03
Version: v0.1.0

Print and Save are OUTPUT_NODEs — they run for their side effect even
when nothing consumes their outputs. torch and ComfyUI modules are
imported lazily so the module imports on any plain python.
'''

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..core import label as core
from ..core.transport import save_stream_file, send_raw_windows
from ..utils.images import label_to_tensor

logger = logging.getLogger(__name__)


def _output_directory() -> str:
    '''ComfyUI's output folder; a local fallback outside the runtime.

    Returns:
        The output directory path.
    '''
    try:
        import folder_paths

        return folder_paths.get_output_directory()
    except ImportError:
        return "./output"


def _save_temp_preview(
    label: core.LabelDocument, filename_prefix: str
) -> dict[str, str] | None:
    '''Write the label bitmap into ComfyUI's temp dir for the node UI.

    Args:
        label: The document to show.
        filename_prefix: Temp file name prefix before the counter.

    Returns:
        The ``images`` entry for the UI response, or None outside the
        ComfyUI runtime (e.g. unit tests on a plain python).
    '''
    try:
        import folder_paths
    except ImportError:
        return None

    folder, filename, counter, subfolder, _ = folder_paths.get_save_image_path(
        filename_prefix,
        folder_paths.get_temp_directory(),
        label.width_dots,
        label.height_dots,
    )
    file = f"{filename}_{counter:05}_.png"
    label.image.save(Path(folder) / file, compress_level=4)
    return {"filename": file, "subfolder": subfolder, "type": "temp"}


def _make_progress_bar(total: int) -> Any:
    '''Create a ComfyUI progress bar; None outside the ComfyUI runtime.

    Args:
        total: Total number of progress steps for the whole operation.

    Returns:
        A fresh ProgressBar, or None when ``comfy`` is not importable
        (e.g. unit tests running on a plain python).
    '''
    try:
        from comfy.utils import ProgressBar
    except ImportError:
        return None
    return ProgressBar(total)


class LabelPreviewNode:
    '''Show the label inside the node and pass it on.

    The in-node preview is pixel-exact: it is the same 1-bit bitmap the
    printer receives — zoom in and each preview pixel is one print dot.
    The LABEL input is returned unchanged (pass-through, so the preview
    can sit mid-chain), and the bitmap also comes out as an IMAGE.
    '''

    CATEGORY = "Lukutar/POS"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, tuple]]:
        return {
            "required": {
                "label": (
                    "LABEL",
                    {"tooltip": "Label to preview (pass-through)"},
                ),
            },
        }

    RETURN_TYPES = ("LABEL", "IMAGE")
    RETURN_NAMES = ("label", "preview")
    FUNCTION = "preview"
    OUTPUT_TOOLTIPS = (
        "The label, unchanged (pass-through)",
        "The 1-bit label bitmap as an RGB IMAGE",
    )

    def preview(self, label: core.LabelDocument) -> dict[str, Any]:
        '''Render the label into the node and pass it through.

        Args:
            label: The document to show.

        Returns:
            Result dict: ``(label, preview IMAGE)`` plus a UI image
            annotation that the frontend draws inside the node.
        '''
        result: dict[str, Any] = {
            "result": (label, label_to_tensor(label)),
        }
        temp_image = _save_temp_preview(label, "LabelPreview")
        if temp_image is not None:
            result["ui"] = {"images": [temp_image]}
        return result


class PrintLabelNode:
    '''Print the label on a Windows POS printer through the RAW spooler.

    Builds the ESC/POS graphic-page payload (``ESC x`` quality,
    ``ESC FD`` raster, ``ESC FA`` print, optional cut) and sends it
    verbatim to the named Windows printer, e.g. ``Custom_TPTCM60``.
    Also returns the printed bitmap as an IMAGE preview.
    '''

    CATEGORY = "Lukutar/POS"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, tuple]]:
        from ..core import FINISH_FEED, FINISH_MODES, QUALITY_HIGH, QUALITY_MODES

        return {
            "required": {
                "label": ("LABEL", {"tooltip": "Label to print"}),
                "printer_name": (
                    "STRING",
                    {
                        "default": "Custom_TPTCM60",
                        "tooltip": (
                            "Windows printer name exactly as in the"
                            " Printers settings"
                        ),
                    },
                ),
                "quality": (
                    list(QUALITY_MODES),
                    {
                        "default": QUALITY_HIGH,
                        "tooltip": (
                            "ESC x n: high quality prints slower but"
                            " sharper"
                        ),
                    },
                ),
                "finish": (
                    list(FINISH_MODES),
                    {
                        "default": FINISH_FEED,
                        "tooltip": (
                            "What happens after the label: nothing, feed,"
                            " total or partial cut (cut needs a cutter)"
                        ),
                    },
                ),
                "copies": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": 999,
                        "tooltip": "Print the same label N times",
                    },
                ),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("preview",)
    FUNCTION = "print_label"

    def print_label(
        self,
        label: core.LabelDocument,
        printer_name: str,
        quality: str,
        finish: str,
        copies: int,
    ) -> tuple[Any]:
        '''Send the label to the printer and return the preview.

        Args:
            label: The document to print.
            printer_name: Windows printer (driver) name.
            quality: One of :data:`core.QUALITY_MODES`.
            finish: One of :data:`core.FINISH_MODES`.
            copies: Repetitions of the whole payload.

        Returns:
            One-element tuple with the printed bitmap as IMAGE.
        '''
        stream = label.to_stream(quality=quality, finish=finish, copies=1)
        bar = _make_progress_bar(copies)
        for i in range(copies):
            send_raw_windows(printer_name, stream)
            if bar is not None:
                bar.update(1)
            logger.info(
                "printed copy %d/%d on %r", i + 1, copies, printer_name
            )
        return (label_to_tensor(label),)


class SaveLabelStreamNode:
    '''Save the raw ESC/POS payload to a file (debug / other transports).

    Writes the exact bytes Print Label would send — useful to inspect
    the stream, archive label templates, or print from any external
    tool that can push bytes to the device.
    '''

    CATEGORY = "Lukutar/POS"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, tuple]]:
        from ..core import FINISH_FEED, FINISH_MODES, QUALITY_HIGH, QUALITY_MODES

        return {
            "required": {
                "label": ("LABEL", {"tooltip": "Label to serialize"}),
                "filename_prefix": (
                    "STRING",
                    {
                        "default": "label",
                        "tooltip": "Output file name prefix",
                    },
                ),
                "quality": (
                    list(QUALITY_MODES),
                    {"default": QUALITY_HIGH},
                ),
                "finish": (
                    list(FINISH_MODES),
                    {"default": FINISH_FEED},
                ),
                "copies": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": 999,
                        "tooltip": "Repeat the payload N times in the file",
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("path",)
    FUNCTION = "save"
    OUTPUT_TOOLTIPS = ("Full path of the written .bin stream",)

    def save(
        self,
        label: core.LabelDocument,
        filename_prefix: str,
        quality: str,
        finish: str,
        copies: int,
    ) -> dict[str, tuple[str] | list[str]]:
        '''Serialize the label and write it next to ComfyUI's output.

        Args:
            label: The document to serialize.
            filename_prefix: File name prefix before the counter.
            quality: One of :data:`core.QUALITY_MODES`.
            finish: One of :data:`core.FINISH_MODES`.
            copies: Repetitions of the payload inside the file.

        Returns:
            Result dict: the file path plus a UI text annotation.
        '''
        stream = label.to_stream(quality=quality, finish=finish, copies=copies)
        path = save_stream_file(
            stream, _output_directory(), filename_prefix
        )
        return {
            "result": (str(path),),
            "ui": {"text": [str(path)]},
        }
