from pathlib import Path
from openpyxl import load_workbook
from openpyxl.drawing.image import Image

from config_loader import machine_config


EXCEL_IMAGE_EMBEDDING_CONFIG = machine_config["excel_image_embedding"]

EMBEDDING_ENABLED = EXCEL_IMAGE_EMBEDDING_CONFIG["enabled"]
SOURCE_IMAGE_SUFFIX = EXCEL_IMAGE_EMBEDDING_CONFIG["source_image_suffix"]
IMAGE_ANCHOR_CELL = EXCEL_IMAGE_EMBEDDING_CONFIG["anchor_cell"]
EMBEDDED_IMAGE_WIDTH = EXCEL_IMAGE_EMBEDDING_CONFIG["image_width"]
EMBEDDED_IMAGE_HEIGHT = EXCEL_IMAGE_EMBEDDING_CONFIG["image_height"]


def embed_h_image_in_excel(
    output_dir: Path,
    file_base_name: str,
    anchor_cell: str = IMAGE_ANCHOR_CELL,
) -> Path | None:
    """
    Embeds the configured standardized image into the standardized output Excel file.

    Important:
    - Only modifies the copied output Excel.
    - Does not touch original Keyence input Excel.
    - Can be disabled in machine_config.toml.
    """

    if not EMBEDDING_ENABLED:
        return None

    excel_path = output_dir / f"{file_base_name}.xlsx"
    image_path = output_dir / f"{file_base_name}{SOURCE_IMAGE_SUFFIX}"

    if not excel_path.exists():
        print(f"WARNING: Excel file not found for image embedding: {excel_path.name}")
        return None

    if not image_path.exists():
        print(f"WARNING: image not found for Excel embedding: {image_path.name}")
        return None

    workbook = load_workbook(excel_path)
    worksheet = workbook.active

    image = Image(image_path)
    image.width = EMBEDDED_IMAGE_WIDTH
    image.height = EMBEDDED_IMAGE_HEIGHT

    worksheet.add_image(image, anchor_cell)

    workbook.save(excel_path)

    return excel_path