# bgrm

`bgrm` is a local CLI for removing image backgrounds and exporting transparent PNGs. It works best on product shots, generated icons, presentation assets, and studio-style images with simple dark or light backgrounds.

The tool can run in two ways:

- `auto` or `ai`: use `rembg` for subject masks, then clean the alpha matte.
- `color-key`: remove simple black or white backgrounds without the AI model.

OpenCV handles the primary alpha cleanup path. A smaller NumPy/Pillow cleanup path remains available if OpenCV cannot import.

## Features

- Process one image or a folder of images.
- Export transparent PNGs.
- Preserve soft edges and interior holes better than plain chroma keying.
- Combine AI masks with black or white background detection in `auto` mode.
- Trim transparent canvas and add consistent padding.
- Generate checkerboard previews for quick review.
- Zip a batch output folder.

## Requirements

- Python 3.10+
- [`uv`](https://docs.astral.sh/uv/) for environment and dependency management

Supported input formats:

- `.png`
- `.jpg`
- `.jpeg`
- `.webp`

## Install

After cloning the repository, install the base environment:

```bash
cd bgrm
uv sync
```

The base install supports `color-key` mode and includes OpenCV cleanup.

Install the AI backend for `auto` and `ai` modes:

```bash
uv sync --extra ai
```

Install test dependencies:

```bash
uv sync --extra test
```

For development with both AI and tests:

```bash
uv sync --extra ai --extra test
```

## Quick Start

Remove a black background from one image without downloading the AI model:

```bash
uv run bgrm input.png --mode color-key --bg black --trim --preview
```

Process a folder with the AI backend:

```bash
uv run bgrm ./input_images \
  --out ./output_images \
  --mode auto \
  --trim \
  --padding 96 \
  --preview \
  --zip
```

Outputs use these names:

```text
input_name_transparent.png
input_name_preview_checker.jpg
output_images.zip
```

## Recommended Recipes

### Product Icons on a Black Background

```bash
uv run bgrm ./icons \
  --out ./icons_transparent \
  --mode auto \
  --bg black \
  --trim \
  --padding 96 \
  --preview \
  --zip \
  --alpha-threshold 6 \
  --edge-feather 1.0 \
  --dilate 1
```

### Product Images on a White Background

```bash
uv run bgrm ./photos \
  --out ./photos_transparent \
  --mode auto \
  --bg white \
  --trim \
  --padding 64 \
  --preview
```

### Fast Local Cutout for Simple Backgrounds

```bash
uv run bgrm input.webp \
  --mode color-key \
  --bg black \
  --trim \
  --padding 48 \
  --preview
```

Use this when the background is close to pure black or pure white and you do not need the AI model.

## CLI Options

```text
input_path                 Image file or folder of images
--out PATH                 Output directory, default: ./background_removed
--mode auto|ai|color-key   Removal mode, default: auto
--bg auto|black|white      Background hint for color-key masking
--trim                     Trim transparent pixels after removal
--padding INT              Transparent padding after trim, default: 64
--preview                  Generate checkerboard preview JPGs
--zip                      Zip the output folder
--keep-soft-shadow         Preserve lower-alpha shadow pixels
--alpha-threshold INT      Remove low-alpha residue, default: 8
--edge-feather FLOAT       Feather mask edges, default: 1.2
--erode INT                Erode mask pixels, default: 0
--dilate INT               Dilate mask pixels, default: 1
```

## How Modes Work

`auto` runs the AI mask first. If the image border looks like a stable black or white background, `bgrm` combines the AI mask with a color-key mask before cleanup.

`ai` uses only the AI mask from `rembg`.

`color-key` uses the background hint from `--bg black` or `--bg white`. It is fast and deterministic, but it works only when the subject separates cleanly from the background color.

## Quality Tips

If a dark halo remains around the subject:

```bash
--alpha-threshold 12 --edge-feather 0.8 --erode 1 --dilate 1
```

If fine detail disappears:

```bash
--alpha-threshold 3 --edge-feather 1.5 --erode 0 --dilate 1
```

If shadows matter:

```bash
--keep-soft-shadow
```

Check preview files on both light and dark backgrounds before using outputs in design tools.

## Troubleshooting

### `rembg is required for --mode auto and --mode ai`

Install the AI extra:

```bash
uv sync --extra ai
```

Or run the deterministic path:

```bash
uv run bgrm input.png --mode color-key --bg black
```

### ONNX Runtime Issues on Apple Silicon

Try the Apple Silicon runtime:

```bash
uv add onnxruntime-silicon
uv remove onnxruntime
```

### The Subject Looks Too Large or Too Small Across a Batch

Use `--trim --padding <pixels>` for each run. Shared-canvas scaling for icon sets is planned but not implemented yet.

## Development

Run tests:

```bash
uv sync --extra test
uv run pytest
```

Check the CLI:

```bash
uv run bgrm --help
```

Project files:

- `remove_background.py`: CLI and processing pipeline
- `tests/`: deterministic tests for masking, trimming, previews, and fallback cleanup
- `Background Removal Tool Spec.md`: original implementation spec

## Status

`bgrm` is an early CLI. The current focus is reliable local batch processing for web, Canva, slide decks, and icon workflows.

## License

MIT. See [LICENSE](LICENSE).
