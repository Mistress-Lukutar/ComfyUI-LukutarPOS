# ComfyUI-LukutarPOS

ComfyUI custom node pack for composing and printing **labels on Custom
TPTCM60 / TPTCM112 kiosk POS printers** (60 mm / 112 mm thermal rolls,
203 DPI, ESC/POS graphic page mode). A label is assembled as a
pass-through chain — Canvas → Image → Text → Barcode → QR → … — then
previewed, printed through the Windows RAW spooler, or saved as a raw
ESC/POS byte stream.

Everything is rasterized into one 1-bit bitmap before printing: text,
barcodes and QR codes are drawn into the page rather than sent as
native printer commands, so **the preview is pixel-exact with the
print** — every preview pixel is one print dot.

## Installation

Clone into `ComfyUI/custom_nodes` and restart ComfyUI:

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/Mistress-Lukutar/ComfyUI-LukutarPOS
```

Dependencies beyond the ComfyUI base (torch, numpy, Pillow ship with
it) are installed by the ComfyUI Manager / registry automatically, or
by hand:

```bash
pip install -r requirements.txt   # segno, python-barcode, pywin32 (Windows)
```

`pywin32` is only needed for actual printing on Windows; composition,
preview and stream saving work everywhere.

## Nodes

Menu category: **`Lukutar/POS`**. All element nodes take a `LABEL`
input and return a new `LABEL` — the document is immutable
(copy-on-write), so any intermediate stage can be previewed, and draw
order is just wire order.

Coordinates and sizes are in **millimetres** (8 dots = 1 mm, 203 DPI);
x grows right, y grows down. Most elements take an `anchor` — a 9-grid
name (`top-left`, `top-center`, …, `center`, …, `bottom-right`) saying
which point of the element's block the (x, y) coordinates refer to.
`ink` selects black or white paint; white ink erases / draws on
`dark_background` canvases.

### Label Canvas

Starts the label. Presets cover the common stock: 60 mm roll
(448-dot printable width) with 20/30/40/60 mm or full-page
(585-dotline) feed, 112 mm roll (832 dots) with 20/30 mm or full-page
(315-dotline) feed, and `custom` (dot widgets; max 832 × the model's
page height). `dark_background` starts the canvas black for
white-ink designs.

### Label Image

Places one frame of a ComfyUI IMAGE batch on the label:

- `fit`: `contain` (whole image inside the box), `cover` (fill the
  box, crop overflow) or `stretch` (distort to exactly the box);
- `dither`: `floyd-steinberg` for photos/gradients, `ordered 2x2/4x4/8x8`
  (Bayer) for crisp line art, `threshold` for already 1-bit artwork;
- `brightness` / `contrast` / `gamma` / `invert` tone controls run
  **before** dithering, so a washed-out generation still prints punchy;
- `frame` picks the batch index to print.

### Label Text

Multiline text (`\n` starts a new line; wire a STRING for dynamic
values) rasterized with a TTF font — the printer's code tables are
never involved, so Cyrillic or any glyph the font has prints fine.
Bundled fonts (DejaVu Sans family): `""`/`default`, `bold`, `mono`;
any name of a file in `assets/fonts/` or an absolute `.ttf`/`.otf`
path also works. `size_mm` is the glyph height in mm; `bold` is a
fake-bold stroke width in dots; `align` aligns lines inside the block.

### Label Barcode

1-D barcode rendered into the bitmap: CODE128 (auto B/C switching),
CODE39, EAN-13, EAN-8, UPC-A, ITF, CODABAR. Checksums are computed
automatically; `module_dots` is the narrow bar width (2 dots scans
reliably at 203 DPI); `quiet_zone_modules` adds white space left/right;
`show_text` prints the HRI text under the bars.

### Label QR Code

QR code via segno (the printer has no native QR). The size follows
from `module_dots`: a version-1 code (21 modules + quiet zone) at
3 dots/module prints ~11 mm wide. `ecc` selects the error correction
level (`l`=7%, `m`=15%, `q`=25%, `h`=30%).

### Label Line / Frame

Rectangle outline or filled block. A filled rectangle of height ~1 mm
is a horizontal rule; an outline rectangle is the classic label border.

### Label Preview

Converts the label into a regular ComfyUI IMAGE — the same 1-bit
bitmap the printer receives, upscaled to RGB.

### Print Label / Windows RAW (output node)

Builds the ESC/POS graphic-page payload — `ESC @` init, `ESC x n`
quality, `ESC FD` raster transfer, `ESC FA` print, `LF`, optional
`ESC i`/`ESC m` cut — and sends it verbatim through the Windows RAW
spooler to `printer_name` (the driver name exactly as in Windows
printer settings, e.g. `Custom_TPTCM60`). `finish` chooses what
happens after the label: `none`, `feed`, `total cut` or `partial cut`
(cut needs a printer with a cutter). `copies` re-sends the payload N
times with a progress bar. Also returns the printed bitmap as IMAGE.

### Save Label Stream / ESC-POS (output node)

Writes the exact bytes Print Label would send to
`ComfyUI/output/<prefix>_NNNNN_.bin` and returns the full path —
useful to inspect the stream, archive templates, or print from any
external tool that can push bytes to the device.

## Printer geometry (TPTCM60/112, manual rev 1.35)

| Model    | Paper  | Print width | Words/dotline | Max page height |
|----------|--------|-------------|---------------|-----------------|
| TPTCM60  | 60 mm  | 448 dots    | 28            | 585 dotlines    |
| TPTCM112 | 112 mm | 832 dots    | 52            | 315 dotlines    |

One `ESC FD` transfer carries at most 16384 16-bit words; the printer
model (and therefore the row padding) is inferred from the label width.

## Development

```bash
pytest                                     # unit tests (no torch needed)
ruff check .                               # lint
mypy --explicit-package-bases core         # type check
"C:/Ai/ComfyUI_windows_portable/python_embeded/python.exe" \
    tests/smoke_test_comfyui_load.py       # node load + e2e, ComfyUI python
```

See `AGENTS.md` for the architecture contract.

## License

MIT. Bundled DejaVu fonts: see `assets/fonts/LICENSE-DejaVuFonts.txt`.
Barcode pattern tables derive from python-barcode (MIT).
