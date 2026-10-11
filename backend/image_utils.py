"""Image decoding and normalization shared by both model stages."""

from pathlib import Path

from PIL import Image, ImageOps


def load_normalized_rgb(image_path: str | Path) -> Image.Image:
    """Return a detached, EXIF-corrected RGB image with alpha composited on white."""
    with Image.open(image_path) as source:
        image = ImageOps.exif_transpose(source)
        if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
            rgba = image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            return Image.alpha_composite(background, rgba).convert("RGB")
        return image.convert("RGB")
