# ComfyUI-LukutarPOS

ComfyUI custom node pack for composing and printing **labels on Custom
TPTCM60 / TPTCM112 kiosk POS printers** (60/112 mm thermal rolls,
203 DPI, ESC/POS graphic page mode).

A label is assembled as a pass-through chain — Canvas → Image → Text →
Barcode → QR → … — then previewed, printed through the Windows RAW
spooler, or saved as a raw ESC/POS byte stream. Everything is
rasterized into a single 1-bit bitmap before printing (text, barcodes
and QR included), so **the preview is pixel-exact with the print**.

## Features

- Full label composition in millimetres with 9-grid anchors — no dot
  math.
- Photo-ready image pipeline: contain/cover/stretch fit, tone controls
  and Floyd–Steinberg / Bayer / threshold dithering.
- Barcodes (CODE128, CODE39, EAN-13/8, UPC-A, ITF, CODABAR) and QR
  codes rendered straight into the bitmap.
- In-node pixel-exact preview, Windows RAW printing with
  quality/finish/copies, or raw ESC/POS stream export.

## Installation

**ComfyUI Manager**: search for `Lukutar POS Nodes` and install —
dependencies are resolved automatically.

**Manually**: clone into `ComfyUI/custom_nodes` and restart ComfyUI:

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/Mistress-Lukutar/ComfyUI-LukutarPOS
```

Extra dependencies (`segno`, `python-barcode`, and `pywin32` on
Windows) are in `requirements.txt`; torch, numpy and Pillow come with
ComfyUI. `pywin32` is only needed for actual printing — composition,
preview and stream saving work everywhere.

## Nodes

Menu category: **`Lukutar/POS`**. Element nodes take a `LABEL` and
return a new immutable `LABEL`, so draw order is just wire order and
any stage can be previewed.

| Node | Purpose |
|------|---------|
| **Label Canvas** | Start a label from a stock preset (60/112 mm rolls) or a custom dot size |
| **Label Image** | Dither one IMAGE frame into a mm box (fit modes, dither methods, tone controls) |
| **Label Image Rotate** | Turn an IMAGE batch so its orientation matches the label — auto aspect-ratio comparison or a fixed 90/180 |
| **Label Text** | Multiline TTF text with font/size/align controls |
| **Label Barcode** | 1-D barcodes with auto checksums and optional HRI text |
| **Label QR Code** | segno-rendered QR with selectable error correction |
| **Label Line / Frame** | Rectangle outline or filled block |
| **Label Preview** | In-node pixel-exact preview; pass-through `LABEL` + `IMAGE` out; the PNG carries prompt/workflow metadata |
| **Print Label / Windows RAW** | Print via the Windows RAW spooler (quality, finish, copies) |
| **Save Label Stream / ESC-POS** | Write the raw ESC/POS payload to a file |

## Printer geometry (TPTCM60/112, manual rev 1.35)

| Model    | Paper  | Print width | Max page height |
|----------|--------|-------------|-----------------|
| TPTCM60  | 60 mm  | 448 dots    | 585 dotlines    |
| TPTCM112 | 112 mm | 832 dots    | 315 dotlines    |

The printer model is inferred from the label width; ESC/POS follows the
graphic page mode subset of the printer manual (`ESC FD` raster
transfer + `ESC FA` print).

## License

MIT. Bundled DejaVu fonts: see `assets/fonts/LICENSE-DejaVuFonts.txt`.
Barcode pattern tables derive from python-barcode (MIT).
