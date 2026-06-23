#!/usr/bin/env python3

from __future__ import annotations

import argparse
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageFilter
from tqdm import tqdm

try:
    import cv2
except ImportError:
    cv2 = None

SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass(frozen=True)
class ProcessOptions:
    mode: str = "auto"
    bg: str = "auto"
    trim: bool = False
    padding: int = 64
    preview: bool = False
    alpha_threshold: int = 8
    edge_feather: float = 1.2
    erode: int = 0
    dilate: int = 1
    keep_soft_shadow: bool = False


def load_rgba(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def estimate_bg_type(rgba: np.ndarray) -> str:
    h, w = rgba.shape[:2]
    border_size = max(1, min(10, h, w))
    border = np.concatenate(
        [
            rgba[:border_size, :, :3].reshape(-1, 3),
            rgba[h - border_size : h, :, :3].reshape(-1, 3),
            rgba[:, :border_size, :3].reshape(-1, 3),
            rgba[:, w - border_size : w, :3].reshape(-1, 3),
        ]
    )

    mean = border.mean(axis=0)
    variance = border.var(axis=0).mean()
    brightness = mean.mean()

    if variance < 500 and brightness < 45:
        return "black"
    if variance < 500 and brightness > 210:
        return "white"
    return "complex"


def color_key_mask(rgba: np.ndarray, bg: str, tolerance: int = 32) -> np.ndarray:
    rgb = rgba[:, :, :3].astype(np.int16)

    if bg == "black":
        distance = np.linalg.norm(rgb, axis=2)
        mask = distance > tolerance
    elif bg == "white":
        distance = np.linalg.norm(255 - rgb, axis=2)
        mask = distance > tolerance
    else:
        mask = np.ones(rgb.shape[:2], dtype=bool)

    return (mask.astype(np.uint8) * 255)


def clean_alpha(
    alpha: np.ndarray,
    alpha_threshold: int = 8,
    dilate: int = 1,
    erode: int = 0,
    feather: float = 1.2,
) -> np.ndarray:
    if alpha_threshold < 0 or alpha_threshold > 255:
        raise ValueError("--alpha-threshold must be between 0 and 255")
    if dilate < 0 or erode < 0:
        raise ValueError("--dilate and --erode must be non-negative")
    if feather < 0:
        raise ValueError("--edge-feather must be non-negative")

    if cv2 is not None:
        return clean_alpha_opencv(
            alpha,
            alpha_threshold=alpha_threshold,
            dilate=dilate,
            erode=erode,
            feather=feather,
        )

    return clean_alpha_fallback(
        alpha,
        alpha_threshold=alpha_threshold,
        dilate=dilate,
        erode=erode,
        feather=feather,
    )


def clean_alpha_opencv(
    alpha: np.ndarray,
    alpha_threshold: int = 8,
    dilate: int = 1,
    erode: int = 0,
    feather: float = 1.2,
) -> np.ndarray:
    mask = alpha.copy()
    mask[mask < alpha_threshold] = 0

    binary = (mask > 0).astype(np.uint8) * 255
    kernel = np.ones((3, 3), np.uint8)

    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)

    if dilate:
        binary = cv2.dilate(binary, kernel, iterations=dilate)
    if erode:
        binary = cv2.erode(binary, kernel, iterations=erode)

    if feather:
        blurred = cv2.GaussianBlur(binary, (0, 0), feather)
        cleaned = np.maximum(mask, blurred)
    else:
        cleaned = np.maximum(mask, binary)

    return np.clip(cleaned, 0, 255).astype(np.uint8)


def clean_alpha_fallback(
    alpha: np.ndarray,
    alpha_threshold: int = 8,
    dilate: int = 1,
    erode: int = 0,
    feather: float = 1.2,
) -> np.ndarray:
    mask = alpha.copy()
    mask[mask < alpha_threshold] = 0

    binary = (mask > 0).astype(np.uint8) * 255

    binary = erode_alpha(dilate_alpha(binary, 1), 1)
    binary = dilate_alpha(erode_alpha(binary, 1), 1)

    if dilate:
        binary = dilate_alpha(binary, dilate)
    if erode:
        binary = erode_alpha(binary, erode)

    if feather:
        blurred = np.array(Image.fromarray(binary, "L").filter(ImageFilter.GaussianBlur(feather)))
        cleaned = np.maximum(mask, blurred)
    else:
        cleaned = np.maximum(mask, binary)

    return np.clip(cleaned, 0, 255).astype(np.uint8)


def dilate_alpha(alpha: np.ndarray, iterations: int) -> np.ndarray:
    result = alpha
    for _ in range(iterations):
        padded = np.pad(result, 1, mode="edge")
        neighborhoods = [
            padded[y : y + result.shape[0], x : x + result.shape[1]]
            for y in range(3)
            for x in range(3)
        ]
        result = np.maximum.reduce(neighborhoods)
    return result.astype(np.uint8)


def erode_alpha(alpha: np.ndarray, iterations: int) -> np.ndarray:
    result = alpha
    for _ in range(iterations):
        padded = np.pad(result, 1, mode="edge")
        neighborhoods = [
            padded[y : y + result.shape[0], x : x + result.shape[1]]
            for y in range(3)
            for x in range(3)
        ]
        result = np.minimum.reduce(neighborhoods)
    return result.astype(np.uint8)


def rembg_alpha(img: Image.Image) -> np.ndarray:
    try:
        from rembg import remove
    except ImportError as exc:
        raise RuntimeError(
            "rembg is required for --mode auto and --mode ai. "
            "Install dependencies with `uv sync` or use --mode color-key."
        ) from exc

    result = remove(img).convert("RGBA")
    return np.array(result)[:, :, 3]


def build_alpha(original: Image.Image, options: ProcessOptions) -> np.ndarray:
    original_arr = np.array(original)
    bg_type = estimate_bg_type(original_arr) if options.bg == "auto" else options.bg

    if options.mode == "color-key":
        if bg_type not in {"black", "white"}:
            raise ValueError("--mode color-key needs --bg black or --bg white for complex backgrounds")
        alpha = color_key_mask(original_arr, bg_type)
    elif options.mode == "ai":
        alpha = rembg_alpha(original)
    else:
        ai_alpha = rembg_alpha(original)
        if bg_type in {"black", "white"}:
            key_alpha = color_key_mask(original_arr, bg_type)
            alpha = np.maximum(ai_alpha, key_alpha)
        else:
            alpha = ai_alpha

    return clean_alpha(
        alpha,
        alpha_threshold=options.alpha_threshold,
        dilate=options.dilate,
        erode=options.erode,
        feather=options.edge_feather,
    )


def apply_alpha(original: Image.Image, alpha: np.ndarray, keep_soft_shadow: bool = False) -> Image.Image:
    rgba = np.array(original).copy()
    rgba[:, :, 3] = alpha

    cutoff = 2 if keep_soft_shadow else 5
    rgba[rgba[:, :, 3] < cutoff, :3] = 0
    rgba[rgba[:, :, 3] < cutoff, 3] = 0

    return Image.fromarray(rgba, "RGBA")


def remove_bg(input_path: Path, options: ProcessOptions) -> Image.Image:
    original = load_rgba(input_path)
    alpha = build_alpha(original, options)
    result = apply_alpha(original, alpha, keep_soft_shadow=options.keep_soft_shadow)

    if options.trim:
        return trim_and_pad(result, options.padding)
    return result


def trim_and_pad(img: Image.Image, padding: int = 64) -> Image.Image:
    if padding < 0:
        raise ValueError("--padding must be non-negative")

    bbox = img.getbbox()
    if not bbox:
        return img

    cropped = img.crop(bbox)
    width, height = cropped.size
    canvas = Image.new("RGBA", (width + padding * 2, height + padding * 2), (0, 0, 0, 0))
    canvas.paste(cropped, (padding, padding), cropped)
    return canvas


def center_on_canvas(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    x = (size[0] - img.width) // 2
    y = (size[1] - img.height) // 2
    canvas.alpha_composite(img, (x, y))
    return canvas


def make_checker_preview(img: Image.Image, tile: int = 32) -> Image.Image:
    width, height = img.size
    bg = Image.new("RGB", (width, height), "white")
    arr = np.array(bg)

    for y in range(0, height, tile):
        for x in range(0, width, tile):
            color = [220, 220, 220] if ((x // tile) + (y // tile)) % 2 == 0 else [245, 245, 245]
            arr[y : y + tile, x : x + tile] = color

    preview = Image.fromarray(arr, "RGB").convert("RGBA")
    preview.alpha_composite(img)
    return preview.convert("RGB")


def collect_inputs(input_path: Path) -> list[Path]:
    if input_path.is_file():
        if input_path.suffix.lower() not in SUPPORTED_EXTS:
            raise ValueError(f"Unsupported file type: {input_path.suffix}")
        return [input_path]

    if not input_path.is_dir():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")

    return sorted(path for path in input_path.iterdir() if path.suffix.lower() in SUPPORTED_EXTS)


def zip_folder(folder: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in folder.rglob("*"):
            if path.is_file() and path.resolve() != zip_path.resolve():
                archive.write(path, path.relative_to(folder.parent))


def process_images(inputs: Iterable[Path], out_dir: Path, options: ProcessOptions) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for path in tqdm(list(inputs), desc="Removing backgrounds"):
        result = remove_bg(path, options)
        out_path = out_dir / f"{path.stem}_transparent.png"
        result.save(out_path)
        written.append(out_path)

        if options.preview:
            preview = make_checker_preview(result)
            preview_path = out_dir / f"{path.stem}_preview_checker.jpg"
            preview.save(preview_path, quality=95)
            written.append(preview_path)

    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Remove image backgrounds and export transparent PNGs.")
    parser.add_argument("input_path", type=Path, help="Image file or folder of images.")
    parser.add_argument("--out", type=Path, default=Path("background_removed"), help="Output directory.")
    parser.add_argument("--mode", choices=["auto", "ai", "color-key"], default="auto")
    parser.add_argument("--bg", choices=["auto", "black", "white"], default="auto")
    parser.add_argument("--trim", action="store_true", help="Trim transparent pixels after removal.")
    parser.add_argument("--padding", type=int, default=64, help="Padding in pixels after trim.")
    parser.add_argument("--preview", action="store_true", help="Generate checkerboard preview JPGs.")
    parser.add_argument("--zip", action="store_true", help="Zip the output directory.")
    parser.add_argument("--keep-soft-shadow", action="store_true", help="Use a lower alpha cutoff for soft shadows.")
    parser.add_argument("--alpha-threshold", type=int, default=8)
    parser.add_argument("--edge-feather", type=float, default=1.2)
    parser.add_argument("--erode", type=int, default=0)
    parser.add_argument("--dilate", type=int, default=1)
    parser.add_argument(
        "--install-apple-silicon-runtime",
        action="store_true",
        help="Print the Apple Silicon onnxruntime-silicon install command and exit.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.install_apple_silicon_runtime:
        print("uv add onnxruntime-silicon && uv remove onnxruntime")
        return

    options = ProcessOptions(
        mode=args.mode,
        bg=args.bg,
        trim=args.trim,
        padding=args.padding,
        preview=args.preview,
        alpha_threshold=args.alpha_threshold,
        edge_feather=args.edge_feather,
        erode=args.erode,
        dilate=args.dilate,
        keep_soft_shadow=args.keep_soft_shadow,
    )

    inputs = collect_inputs(args.input_path)
    if not inputs:
        raise SystemExit(f"No supported images found in {args.input_path}")

    written = process_images(inputs, args.out, options)

    if args.zip:
        zip_path = args.out.parent / f"{args.out.name}.zip"
        if zip_path.exists():
            zip_path.unlink()
        zip_folder(args.out, zip_path)
        written.append(zip_path)

    print(f"Wrote {len(written)} file(s) to {args.out}")


if __name__ == "__main__":
    main()
