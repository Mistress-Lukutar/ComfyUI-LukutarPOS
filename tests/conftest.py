'''
File:   conftest.py
Brief:  Pytest bootstrap: load the torch-free subpackages for unit tests.
Author: Mistress-Lukutar
Date:   2026-09-03
Version: v0.1.0

Loads ``core``, ``utils`` and the node modules under an import alias
(the real folder name has a hyphen and cannot be imported). Everything
except the tensor glue is torch-free, so the engine tests run under any
python with numpy, Pillow, segno and python-barcode — no torch needed.
Node-level IMAGE glue is validated by ``tests/smoke_test_comfyui_load.py``
under ComfyUI's own python.
'''

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parent.parent
#: Import alias: the real folder name has a hyphen and cannot be imported.
PACKAGE_ALIAS = "comfyui_lukutar_pos"


def _load_subpackage(name: str) -> types.ModuleType:
    '''Expose a subpackage under the alias without executing the root
    ``__init__.py`` (it is the ComfyUI entry point, not a package
    initializer for tests).

    Args:
        name: Subpackage name ("core", "utils", "nodes").

    Returns:
        The imported subpackage module.
    '''
    full = f"{PACKAGE_ALIAS}.{name}"
    if full in sys.modules:
        return sys.modules[full]
    if PACKAGE_ALIAS not in sys.modules:
        parent = types.ModuleType(PACKAGE_ALIAS)
        parent.__path__ = [str(PACK_ROOT)]
        sys.modules[PACKAGE_ALIAS] = parent
    return importlib.import_module(full)


_load_subpackage("core")
_load_subpackage("utils")
_load_subpackage("nodes")
