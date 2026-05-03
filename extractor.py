from pathlib import Path
from dataclasses import dataclass, asdict
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

@dataclass
class Measurement:
    nr: str | None
    measurement_name: str | None
    elem_1: str | None
    detail: str | None
    elem_2: str | None
    kommentar: str | None
    classification: str | None
    value: str | None
    unit: str | None
    target: str | None
    upper_tolerance: str | None
    lower_tolerance: str | None

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

def normalize_positions(metadata_list: list[CellMetadata]) -> dict[str, str]:
    raw_positions = []

    for metadata in metadata_list:
        if metadata.position is not None:
            raw_positions.append(metadata.position)

    sorted_positions = sorted(raw_positions, key=lambda pos: int(pos))

    position_mapping = {}

    for index, raw_position in enumerate(sorted_positions, start=1):
        normalized_position = f"{index:02d}"
        position_mapping[raw_position] = normalized_position

    return position_mapping

def extract_measurements_from_excel(excel_file: Path) -> list[Measurement]:
    workbook = load_workbook(excel_file, data_only=True, read_only=True)

    measurements = []

    try:
        sheet = workbook.active
        row = 32

        while True:
            nr = clean_cell_value(sheet[f"B{row}"].value)
            measurement_name = clean_cell_value(sheet[f"C{row}"].value)

            if nr is None:
                break

            measurement = Measurement(
                nr=nr,
                measurement_name=measurement_name,
                elem_1=clean_cell_value(sheet[f"D{row}"].value),
                detail=clean_cell_value(sheet[f"E{row}"].value),
                elem_2=clean_cell_value(sheet[f"F{row}"].value),
                kommentar=clean_cell_value(sheet[f"G{row}"].value),
                classification=clean_cell_value(sheet[f"H{row}"].value),
                value=clean_cell_value(sheet[f"I{row}"].value),
                unit=clean_cell_value(sheet[f"J{row}"].value),
                target=clean_cell_value(sheet[f"K{row}"].value),
                upper_tolerance=clean_cell_value(sheet[f"L{row}"].value),
                lower_tolerance=clean_cell_value(sheet[f"M{row}"].value),
            )

            measurements.append(measurement)
            row += 1

    finally:
        workbook.close()

    return measurements

def determine_quality(metadata: CellMetadata) -> str:
    if metadata.overall_result is not None and metadata.overall_result.lower() == "ok":
        return "IO"

    return "NIO"


def build_cell_data(file_group: list[Path]) -> list[dict]:
    metadata_list = extract_metadata(file_group)
    position_mapping = normalize_positions(metadata_list)

    cell_data_list = []

    for metadata in metadata_list:
        normalized_position = position_mapping[metadata.position]
        cell_dmc = f"{metadata.leadframe_dmc}-{normalized_position}"

        excel_file = next(
            file for file in file_group
            if file.name == metadata.source_file
        )

        measurements = extract_measurements_from_excel(excel_file)
        quality = determine_quality(metadata)

        cell_data = {
            "source_file": metadata.source_file,
            "timestamp": metadata.timestamp,
            "leadframe_dmc": metadata.leadframe_dmc,
            "raw_position": metadata.position,
            "position": normalized_position,
            "cell_dmc": cell_dmc,
            "name": metadata.name,
            "product_name": metadata.product_name,
            "device": metadata.device,
            "overall_result": metadata.overall_result,
            "quality": quality,
            "measurements": [
                asdict(measurement)
                for measurement in measurements
            ],
        }

        cell_data_list.append(cell_data)

    return cell_data_list