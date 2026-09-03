# AGENTS.md — ComfyUI-LukutarPOS

ComfyUI custom node pack by Mistress-Lukutar: composes 1-bit labels for
Custom **TPTCM60 / TPTCM112** kiosk POS printers (60/112 mm thermal
rolls, 203 DPI = 8 dots/mm) and prints them in ESC/POS **graphic page
mode** (`ESC FD` raster transfer + `ESC FA` print).

Nodes (menu category `Lukutar/POS`):
**Label Canvas** — starts the immutable `LABEL` document (stock presets
or custom dot size, optional dark background); **Label Image** —
dithers one IMAGE frame into a mm box (contain/cover/stretch,
Floyd-Steinberg / Bayer / threshold, tone controls before dithering);
**Label Text** — TTF text (bundled DejaVu faces, Cyrillic-safe, fake
bold, 9-grid anchor, per-line align); **Label Barcode** — CODE128 /
CODE39 / EAN-13 / EAN-8 / UPC-A / ITF / CODABAR rendered into the
bitmap with auto checksums and optional HRI; **Label QR Code** —
segno-rendered QR; **Label Line / Frame** — rectangle outline or filled
block; **Label Preview** — in-node pixel-exact preview (output node,
pass-through `LABEL` + `IMAGE` out); **Print Label /
Windows RAW** — RAW-spooler printing with quality/finish/copies;
**Save Label Stream / ESC-POS** — writes the raw payload to a file.

The nodes' behavioral contract (inputs, units, anchor semantics, ESC/POS
command subset) is specified in `README.md`; keep the README in sync
with any behavior change.

## Layout & architecture boundaries

- `core/` — pure engines: `label.py` (1-bit compositor, PIL),
  `dithering.py`, `barcode.py` (module matrices, python-barcode
  charsets), `escpos.py` (byte-stream builder, no I/O), `transport.py`
  (Windows RAW spooler + file sink). **No ComfyUI imports, no torch** —
  must stay importable and unit-testable on any plain python that has
  numpy, Pillow, segno and python-barcode. pywin32 is imported lazily
  inside `send_raw_windows`.
- `nodes/` — ComfyUI node classes (`INPUT_TYPES`, tensor glue). The
  element nodes are torch-free; only `Label Image` touches a tensor,
  exclusively through `utils/images.py`. ComfyUI imports must be lazy
  and guarded (`try: from comfy... except ImportError: return None`,
  pattern: `_make_progress_bar` in `nodes/label_output.py`).
- `utils/` — torch IMAGE-tensor ⇄ numpy conversion helpers (torch
  imported lazily inside the functions).
- `web/` — frontend extension served via `WEB_DIRECTORY` (Label Canvas
  greys out the dot-size widgets unless the preset is `custom`).
- `assets/fonts/` — bundled DejaVu TTFs resolvable by name (`""`,
  `bold`, `mono`); any absolute .ttf/.otf path also works.
- `tests/unit/` — engine + node tests, torch-free.
  `tests/smoke_test_comfyui_load.py` — node loading + end-to-end label
  composition, ComfyUI's embedded python only.

Adding a node: logic in `core/`, node class in `nodes/`, then register
it in `nodes/__init__.py` (`NODE_CLASS_MAPPINGS` +
`NODE_DISPLAY_NAME_MAPPINGS`, plain display names without a pack
suffix).

## Key contracts

- A `LABEL` is an immutable `LabelDocument` (PIL mode-`1` image, 0 =
  black ink, 255 = white paper). Every draw operation is copy-on-write
  and returns a new document — never mutate in place.
- User-facing positions/sizes are **millimetres**, converted with
  `mm_to_dots` (8 dots/mm). `anchor` is a 9-grid name resolved by
  `anchor_offset`.
- ESC/POS subset follows the printer manual rev 1.35 §3.2.2; the G
  model (448 dots, 28 words/dotline, 585 dotlines) vs H model (832/52/
  315) geometry lives in `core/escpos.py`, and the model is inferred
  from the label width. One `ESC FD` transfer ≤ 16384 words.
- Barcodes and QR are rasterized into the bitmap (no native `GS k` /
  `GS ( k` commands) so preview matches print exactly.

## Commands

```bash
# Unit tests — any python with numpy, Pillow, segno, python-barcode,
# pytest (no torch)
pytest

# Lint (ruff: line-length 88, rules E,F,W,I,UP,B,SIM)
ruff check .

# Type check — plain `mypy core` FAILS (hyphenated repo folder); use:
mypy --explicit-package-bases core

# Node load + e2e smoke test — MUST use ComfyUI's embedded python
"C:/Ai/ComfyUI_windows_portable/python_embeded/python.exe" tests/smoke_test_comfyui_load.py
```

The pack is **not pip-installed**; it is cloned into
`ComfyUI/custom_nodes`. `requirements.txt` carries `segno`,
`python-barcode` and `pywin32` (Windows only) — torch, numpy and Pillow
come from the ComfyUI runtime. The `[project]`/`[tool.comfy]` tables in
`pyproject.toml` are registry + package metadata (no pip semantics);
pytest/ruff/mypy config lives in its tool sections.

## Releases (ComfyUI registry)

Published by CI, never by hand. Pushing a `v*` tag (or pressing "Run
workflow" in the Actions tab) makes `.github/workflows/publish_action.yml`
run Comfy-Org/publish-node-action with the `REGISTRY_ACCESS_TOKEN` repo
secret and publish the version written in `pyproject.toml` to the
registry — publisher `mistress-lukutar`, node id `lukutar-pos-nodes`.

```bash
# checks green first: pytest, ruff, mypy, smoke test (see Commands)
# bump the version in BOTH __init__.py.__version__ and pyproject.toml
git commit -m "chore(release): bump version to X.Y.Z"
git tag vX.Y.Z
git push origin main --tags
```

- Verify: `gh run list --workflow=publish_action.yml` (expect success),
  then `curl -s https://api.comfy.org/nodes/lukutar-pos-nodes/versions`
  must list the new version.
- A published version can never be republished — the registry answers
  400 "The node version already exists". A forgotten bump = red run.
- The registry node name (`lukutar-pos-nodes` in `pyproject.toml`) is
  immutable after the first publish; `DisplayName` is changeable.
- The workflow deliberately does NOT fire on `pyproject.toml` edits:
  the file changes for non-release reasons too. The tag is the release.
- The package is every git-tracked file minus `.comfyignore` — when
  adding dev-only files, extend `.comfyignore` so they don't ship.

## Import / pytest gotchas

- The repo folder name contains a hyphen and is **not a valid python
  package name**. Consequences:
  - mypy errors with "not a valid Python package name" unless run with
    `--explicit-package-bases`.
  - Unit tests import the subpackages through a stub parent package
    aliased `comfyui_lukutar_pos` (`tests/conftest.py`), which
    deliberately does **not** execute the root `__init__.py`.
- pytest runs with `--import-mode=importlib` and root `conftest.py` sets
  `collect_ignore = ["__init__.py"]` — don't remove either; pytest 9
  would otherwise try to import the root `__init__` and fail.
- Root `__init__.py` is dual-mode: imported as a package it exports the
  real node mappings; imported as a bare module (no package context) it
  exposes empty mappings instead of failing. ComfyUI never takes the
  bare-module branch.

## Conventions

- Python >= 3.10. Every module starts with the header docstring
  (`File / Brief / Author / Date / Version`) followed by
  `from __future__ import annotations`. Docstrings use triple
  single-quotes (`'''`).
- Google-style docstrings (`Args:` / `Returns:` / `Raises:`); `#:` doc
  comments on module constants; combo choices exposed as module-level
  string tuples (e.g. `DITHER_METHODS` in `core/dithering.py`) and
  re-exported via the package `__init__` `__all__`.
- Use module loggers (`logging.getLogger(__name__)`), not print.
- Version is tracked in **both** `__init__.py.__version__` and
  `pyproject.toml` — bump them together (release flow: see Releases).
