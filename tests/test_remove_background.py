from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

from remove_background import (
    ProcessOptions,
    clean_alpha,
    clean_alpha_fallback,
    collect_inputs,
    color_key_mask,
    estimate_bg_type,
    make_checker_preview,
    remove_bg,
    trim_and_pad,
    zip_folder,
)


def test_estimate_bg_type_detects_simple_backgrounds() -> None:
    black = np.zeros((24, 24, 4), dtype=np.uint8)
    white = np.full((24, 24, 4), 255, dtype=np.uint8)
    complex_bg = np.zeros((24, 24, 4), dtype=np.uint8)
    complex_bg[:, ::2, :3] = [255, 0, 0]
    complex_bg[:, 1::2, :3] = [0, 255, 0]
    complex_bg[:, :, 3] = 255

    assert estimate_bg_type(black) == "black"
    assert estimate_bg_type(white) == "white"
    assert estimate_bg_type(complex_bg) == "complex"


def test_color_key_mask_keeps_subject_on_black() -> None:
    rgba = np.zeros((5, 5, 4), dtype=np.uint8)
    rgba[:, :, 3] = 255
    rgba[2, 2, :3] = [240, 20, 20]

    mask = color_key_mask(rgba, "black", tolerance=32)

    assert mask[0, 0] == 0
    assert mask[2, 2] == 255


def test_clean_alpha_fallback_matches_public_shape(monkeypatch) -> None:
    alpha = np.zeros((5, 5), dtype=np.uint8)
    alpha[2, 2] = 255

    fallback = clean_alpha_fallback(alpha, feather=0, dilate=1)

    monkeypatch.setattr("remove_background.cv2", None)
    public = clean_alpha(alpha, feather=0, dilate=1)

    assert fallback.shape == alpha.shape
    assert public.shape == alpha.shape
    assert public.dtype == np.uint8
    assert public[2, 2] == 255


def test_trim_and_pad_crops_to_subject() -> None:
    img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    img.putpixel((4, 5), (255, 0, 0, 255))

    result = trim_and_pad(img, padding=2)

    assert result.size == (5, 5)
    assert result.getpixel((2, 2)) == (255, 0, 0, 255)


def test_color_key_mode_removes_black_without_rembg(tmp_path: Path) -> None:
    image_path = tmp_path / "icon.png"
    img = Image.new("RGBA", (8, 8), (0, 0, 0, 255))
    for x in range(2, 6):
        for y in range(2, 6):
            img.putpixel((x, y), (255, 255, 255, 255))
    img.save(image_path)

    result = remove_bg(
        image_path,
        ProcessOptions(mode="color-key", bg="black", trim=True, padding=1, edge_feather=0, dilate=0),
    )

    assert result.mode == "RGBA"
    assert result.size == (6, 6)
    assert result.getpixel((0, 0))[3] == 0
    assert result.getpixel((3, 3))[3] == 255


def test_collect_inputs_filters_supported_extensions(tmp_path: Path) -> None:
    (tmp_path / "a.png").write_bytes(b"")
    (tmp_path / "b.webp").write_bytes(b"")
    (tmp_path / "c.txt").write_text("nope")

    assert [path.name for path in collect_inputs(tmp_path)] == ["a.png", "b.webp"]


def test_preview_and_zip_outputs(tmp_path: Path) -> None:
    img = Image.new("RGBA", (6, 6), (0, 0, 0, 0))
    img.putpixel((2, 2), (255, 0, 0, 255))
    preview = make_checker_preview(img, tile=2)
    assert preview.mode == "RGB"

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "result.png").write_bytes(b"png")
    zip_path = tmp_path / "out.zip"
    zip_folder(out_dir, zip_path)

    with zipfile.ZipFile(zip_path) as archive:
        assert archive.namelist() == ["out/result.png"]
