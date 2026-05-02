from pathlib import Path
from dataclasses import dataclass
from openpyxl import load_workbook


@dataclass
class ValidationResult:
    valid: bool
    dmc: str | None
    reason: str | None = None


def find_excel_files(file_group: list[Path]) -> list[Path]:
    return [
        file_path
        for file_path in file_group
        if file_path.suffix.lower() == ".xlsx"
    ]


def read_dmc_from_excel(excel_file: Path) -> str | None:
    workbook = load_workbook(excel_file, data_only=True, read_only=True)
    sheet = workbook.active

    value = sheet["I17"].value

    workbook.close()

    if value is None:
        return None

    dmc = str(value).strip()

    if dmc == "":
        return None

    return dmc


def validate_group(file_group: list[Path]) -> ValidationResult:
    excel_files = find_excel_files(file_group)

    if not excel_files:
        return ValidationResult(
            valid=False,
            dmc=None,
            reason="No Excel file found in group"
        )

    for excel_file in excel_files:
        dmc = read_dmc_from_excel(excel_file)

        if dmc is not None:
            return ValidationResult(
                valid=True,
                dmc=dmc,
                reason=None
            )

    return ValidationResult(
        valid=False,
        dmc=None,
        reason="No DMC found in Excel cell I17"
    )