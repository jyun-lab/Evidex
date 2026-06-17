from pathlib import Path


IMAGE_EXTENSIONS = {
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}


def is_image_path(path):
    """Return True when a path looks like a directly previewable image file."""
    return Path(str(path)).suffix.lower() in IMAGE_EXTENSIONS
