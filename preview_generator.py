from pathlib import Path
from PIL import Image

from config_loader import machine_config


PREVIEW_CONFIG = machine_config["preview"]

PREVIEW_SIZE = (
    PREVIEW_CONFIG["preview_width"],
    PREVIEW_CONFIG["preview_height"],
)

PREVIEW_SOURCE_SUFFIXES = PREVIEW_CONFIG["preview_source_suffixes"]


def create_preview_for_image(image_path: Path) -> Path:
    """
    Creates a preview image for one exported image.
    Original image stays unchanged.

    Example:
    ..._h.png -> ..._h_preview.png
    ..._t.png -> ..._t_preview.png
    """

    preview_path = image_path.with_name(f"{image_path.stem}_preview{image_path.suffix}")

    with Image.open(image_path) as img:
        img = img.copy()
        img.thumbnail(PREVIEW_SIZE)

        preview = Image.new("RGB", PREVIEW_SIZE, "white")

        x = (PREVIEW_SIZE[0] - img.width) // 2
        y = (PREVIEW_SIZE[1] - img.height) // 2

        preview.paste(img.convert("RGB"), (x, y))
        preview.save(preview_path)

    return preview_path


def has_configured_preview_suffix(image_path: Path) -> bool:
    return any(
        image_path.name.endswith(source_suffix)
        for source_suffix in PREVIEW_SOURCE_SUFFIXES
    )


def generate_previews(output_dir: Path) -> list[Path]:
    """
    Generates previews for all configured exported image suffixes.
    Existing previews are skipped.
    """

    created_previews = []

    image_paths = [
        file_path
        for file_path in output_dir.iterdir()
        if file_path.is_file()
        and has_configured_preview_suffix(file_path)
    ]

    for image_path in image_paths:
        if image_path.stem.endswith("_preview"):
            continue

        preview_path = image_path.with_name(f"{image_path.stem}_preview{image_path.suffix}")

        if preview_path.exists():
            continue

        created_preview = create_preview_for_image(image_path)
        created_previews.append(created_preview)

    return created_previews