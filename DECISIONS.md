# Decisions

## 2026-06-23 - Use a Python CLI MVP

The tool starts as a Python command-line utility because the source spec is CLI-first and the main dependencies (`rembg`, OpenCV, Pillow) are Python-native.

## 2026-06-23 - Lazy-load `rembg`

`rembg` is imported only for `auto` and `ai` modes. This lets `color-key` mode and the deterministic test suite run without forcing an AI model load or ONNX runtime setup.

## 2026-06-23 - Keep the AI backend optional

The base install excludes `rembg` because its transitive runtime stack can vary by Python and CPU architecture. The deterministic CLI path installs cleanly by default, and AI mode is available through the `ai` extra.

The `ai` extra pins `numba>=0.63` so Python 3.11 does not resolve to the older `numba 0.53` and `llvmlite 0.36` pair.

## 2026-06-23 - Prefer OpenCV cleanup with a fallback

OpenCV is the primary alpha cleanup backend because its morphology and Gaussian blur operations are the quality baseline from the original spec. A small NumPy/Pillow cleanup path remains as a fallback for stripped-down environments where OpenCV is unavailable.
