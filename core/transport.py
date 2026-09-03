'''
File:   transport.py
Brief:  Byte-stream sinks: Windows RAW spooler print and file output.
Author: Mistress-Lukutar
Date:   2026-09-03
Version: v0.1.0

The RAW transport opens the Windows printer by its driver name (e.g.
``Custom_TPTCM60``) and writes the ESC/POS stream verbatim through the
spooler — the same path the working test script used. pywin32 is
imported lazily so the module (and the whole pack) stays importable
on any python; only an actual print needs the dependency.
'''

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def send_raw_windows(printer_name: str, data: bytes) -> None:
    '''Send a raw byte stream to a Windows printer via the spooler.

    Args:
        printer_name: Windows printer (driver) name, e.g.
            ``Custom_TPTCM60``.
        data: Raw ESC/POS payload.

    Raises:
        ImportError: When pywin32 is not installed.
        RuntimeError: When the spooler rejects the open/write.
    '''
    try:
        import win32print
    except ImportError as exc:  # pragma: no cover - platform dependent
        raise ImportError(
            "Windows RAW printing needs pywin32 (pip install pywin32)"
        ) from exc

    try:
        handle = win32print.OpenPrinter(printer_name)
    except Exception as exc:
        raise RuntimeError(
            f"cannot open Windows printer {printer_name!r} — check the"
            " exact name in Windows printer settings"
        ) from exc
    try:
        win32print.StartDocPrinter(handle, 1, ("Label", None, "RAW"))
        try:
            win32print.WritePrinter(handle, data)
        finally:
            win32print.EndDocPrinter(handle)
    except Exception as exc:
        raise RuntimeError(
            f"Windows spooler failed while printing to {printer_name!r}"
        ) from exc
    finally:
        win32print.ClosePrinter(handle)
    logger.info(
        "sent %d bytes to Windows printer %r", len(data), printer_name
    )


def save_stream_file(
    data: bytes, directory: str, filename_prefix: str
) -> Path:
    '''Write an ESC/POS stream to a numbered file, ComfyUI-style.

    Follows the save-node convention: ``<directory>/<prefix>00001.bin``,
    incrementing the five-digit counter until a free name is found.

    Args:
        data: Raw ESC/POS payload.
        directory: Output folder (created when missing).
        filename_prefix: File name prefix before the counter.

    Returns:
        The path of the file written.
    '''
    out_dir = Path(directory)
    out_dir.mkdir(parents=True, exist_ok=True)
    counter = 1
    path = out_dir / f"{filename_prefix}{counter:05d}.bin"
    while path.exists():
        counter += 1
        path = out_dir / f"{filename_prefix}{counter:05d}.bin"
    path.write_bytes(data)
    logger.info("saved %d bytes to %s", len(data), path)
    return path
