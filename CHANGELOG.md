# Changelog

## 2026-06-24

- Rewrote the README for public repo use with install paths, recipes, CLI reference, quality tips, and troubleshooting.
- Added an MIT license for public release.

## 2026-06-23

- Built the initial background-removal CLI with AI, color-key, trim, preview, and zip support.
- Added project packaging, README usage notes, and focused tests for deterministic image-processing helpers.
- Kept the AI backend optional and made OpenCV the primary alpha cleanup backend, with NumPy/Pillow as a fallback.
