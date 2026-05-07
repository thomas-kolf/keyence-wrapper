from pathlib import Path
from openpyxl import load_workbook
from openpyxl.drawing.image import Image


DEFAULT_IMAGE_WIDTH = 320
DEFAULT_IMAGE_HEIGHT = 240
IMAGE_ANCHOR_CELL = "E7"


def _get_existing_image_size(worksheet) -> tuple[int, int]:
    """
    Reads the size of the first already existing image in the worksheet.
    If no image exists, fallback size is used.
    """

    existing_images = getattr(worksheet, "_images", [])

    if not existing_images:
        return DEFAULT_IMAGE_WIDTH, DEFAULT_IMAGE_HEIGHT

    first_image = existing_images[0]

    return int(first_image.width), int(first_image.height)


def embed_h_image_in_excel(
    output_dir: Path,
    file_base_name: str,
    anchor_cell: str = IMAGE_ANCHOR_CELL,
) -> Path | None:
    """
    Embeds the standardized original _h.png into the standardized output Excel file.

    Important:
    - Only modifies the copied output Excel.
    - Does not touch original Keyence input Excel.
    - Uses the same size as the first image already present in the sheet.
    """

    excel_path = output_dir / f"{file_base_name}.xlsx"
    image_path = output_dir / f"{file_base_name}_h.png"

    if not excel_path.exists():
        print(f"WARNING: Excel file not found for image embedding: {excel_path.name}")
        return None

    if not image_path.exists():
        print(f"WARNING: _h image not found for Excel embedding: {image_path.name}")
        return None

    workbook = load_workbook(excel_path)
    worksheet = workbook.active

    image_width, image_height = _get_existing_image_size(worksheet)

    image = Image(image_path)
    image.width = image_width
    image.height = image_height

    worksheet.add_image(image, anchor_cell)

    workbook.save(excel_path)

    return excel_path