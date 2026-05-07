from pathlib import Path
from openpyxl import load_workbook
from openpyxl.drawing.image import Image


EMBEDDED_IMAGE_WIDTH = 285
EMBEDDED_IMAGE_HEIGHT = 300
IMAGE_ANCHOR_CELL = "E7"


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
    - Uses a fixed image size close to the existing Keyence report image.
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

    image = Image(image_path)
    image.width = EMBEDDED_IMAGE_WIDTH
    image.height = EMBEDDED_IMAGE_HEIGHT

    worksheet.add_image(image, anchor_cell)

    workbook.save(excel_path)

    return excel_path