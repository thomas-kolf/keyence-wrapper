from pathlib import Path
from dataclasses import dataclass
from openpyxl import load_workbook


@dataclass
class CellMetadata:
    source_file: str
    timestamp: str | None
    leadframe_dmc: str | None
    position: str | None
    name: str | None
    product_name: str | None
    device: str | None
    overall_result: str | None


def find_excel_files(file_group: list[Path]) -> list[Path]:
    return [
        file_path
        for file_path in file_group
        if file_path.suffix.lower() == ".xlsx"
    ]


def clean_cell_value(value) -> str | None:
    if value is None:
        return None

    value = str(value).strip()

    if value == "":
        return None

    return value


def read_metadata_from_excel(excel_file: Path) -> CellMetadata:
    workbook = load_workbook(excel_file, data_only=True, read_only=True)

    try:
        sheet = workbook.active

        return CellMetadata(
            source_file=excel_file.name,
            timestamp=clean_cell_value(sheet["I16"].value),
            leadframe_dmc=clean_cell_value(sheet["I17"].value),
            position=clean_cell_value(sheet["I18"].value),
            name=clean_cell_value(sheet["I19"].value),
            product_name=clean_cell_value(sheet["I20"].value),
            device=clean_cell_value(sheet["I24"].value),
            overall_result=clean_cell_value(sheet["I25"].value),
        )

    finally:
        workbook.close()


def extract_metadata(file_group: list[Path]) -> list[CellMetadata]:
    excel_files = find_excel_files(file_group)

    metadata_list = []

    for excel_file in excel_files:
        metadata = read_metadata_from_excel(excel_file)
        metadata_list.append(metadata)

    return metadata_list