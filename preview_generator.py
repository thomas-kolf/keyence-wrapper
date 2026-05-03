from pathlib import Path
from PIL import Image


PREVIEW_SIZE = (160, 120)


def create_preview_for_image(image_path: Path) -> Path:
    """
    Creates a 160x120 preview image for one exported Keyence image.
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


def generate_previews(output_dir: Path) -> list[Path]:
    """
    Generates previews for all exported _h.png and _t.png images.
    Existing previews are skipped.
    """

    created_previews = []

    image_paths = list(output_dir.glob("*_h.png")) + list(output_dir.glob("*_t.png"))

    for image_path in image_paths:
        if image_path.stem.endswith("_preview"):
            continue

        preview_path = image_path.with_name(f"{image_path.stem}_preview{image_path.suffix}")

        if preview_path.exists():
            continue

        created_preview = create_preview_for_image(image_path)
        created_previews.append(created_preview)

    return created_previews