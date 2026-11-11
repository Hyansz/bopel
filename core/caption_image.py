"""Utility to embed caption text into screenshot PNGs.

Adds a dark horizontal band at the top of the image containing a caption:
    "Shopee Ads <Nama Toko> <MM> <DD> <YYYY>"
The caption text is derived from the image filename (store name part before the first underscore).
The function respects the config flag ``caption_di_gambar`` defined under the
``Screenshot Iklan`` tool in ``config.yaml`` – if the flag is false the original
image path is returned unchanged.
"""

from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

# Local import to avoid circular import at module load time
from core.config import Config


def _load_font(max_width: int, max_height: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a bold font that fits within the given dimensions.
    Tries common Windows fonts, falls back to the default PIL bitmap font.
    """
    # Desired font size is roughly half the band height
    font_size = max(12, int(max_height * 0.5))
    for font_path in [
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, font_size)
            except Exception:
                continue
    # fallback
    return ImageFont.load_default()


def add_caption_to_image(image_path: Path | str) -> Path:
    """Add caption band to *image_path* and return the path of the new image.

    The caption text uses the format ``"Shopee Ads <Nama Toko> <MM> <DD> <YYYY>"``.
    ``<Nama Toko>`` is taken from the filename (everything before the first ``_``).
    The new image is stored under ``logs/screenshots/iklan/captioned/`` keeping the
    original filename. If the config flag ``caption_di_gambar`` is falsy the original
    path is returned unchanged.
    """
    img_path = Path(image_path)
    # Load config flag – safe guard if config not loaded yet
    Config.ensure_loaded()
    # Find the tool entry for screenshot_iklan.py
    flag = False
    for tool in Config.tools():
        if tool.get("script") == "screenshot_iklan.py":
            flag = bool(tool.get("caption_di_gambar", True))
            break
    if not flag:
        return img_path

    if not img_path.exists():
        raise FileNotFoundError(f"Image not found: {img_path}")

    # Derive store name from filename using shared helper
    from core.store_name import nama_toko_dari_file
    store_name = nama_toko_dari_file(img_path) or stem.split("_")[0]

    today = datetime.now()
    caption = f"Shopee Ads {store_name} {today.month:02d} {today.day:02d} {today.year:04d}"

    # Open original image
    img = Image.open(img_path)
    w, h = img.size
    # Height of the caption band: at least 56px, otherwise ~7% of original height
    band_h = max(56, int(h * 0.07))
    # Create new image with extra band on top, dark background
    new_img = Image.new("RGB", (w, h + band_h), (30, 30, 30))
    new_img.paste(img, (0, band_h))
    draw = ImageDraw.Draw(new_img)
    font = _load_font(w, band_h)
    # Simple left padding
    padding = 10
    # get text size
    bbox = draw.textbbox((0, 0), caption, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    draw.text((padding, (band_h - text_height) // 2), caption, fill=(255, 255, 255), font=font)

    # Destination path – keep same filename under captioned subfolder
    dest_dir = img_path.parent / "captioned"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / img_path.name
    new_img.save(dest_path)
    return dest_path
