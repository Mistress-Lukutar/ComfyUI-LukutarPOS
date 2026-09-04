'''
File:   __init__.py
Brief:  ComfyUI-LukutarPOS custom node pack entry point.
Author: Mistress-Lukutar
Date:   2026-09-03
Version: v0.1.0
'''

from __future__ import annotations

__version__ = "0.2.0"

#: Frontend extension files (ComfyUI serves them to the browser).
WEB_DIRECTORY = "./web"

if __package__:
    # Normal case: imported as a package (ComfyUI's custom node loader,
    # smoke test) — relative imports resolve as usual.
    from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
else:
    # Imported as a bare module (e.g. pytest 9 imports the rootdir package
    # __init__ without package context). The real node modules stay
    # importable here (torch is only pulled lazily inside the IMAGE glue),
    # but keep the bare branch mapping-free for symmetry with the loader
    # contract; ComfyUI itself never takes this branch.
    NODE_CLASS_MAPPINGS: dict[str, type] = {}
    NODE_DISPLAY_NAME_MAPPINGS: dict[str, str] = {}

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
    "__version__",
]
