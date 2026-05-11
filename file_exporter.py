from pathlib import Path
import shutil
import re

from config_loader import machine_config


RAW_FILES_CONFIG = machine_config["raw_files"]
FILE_STRUCTURE_CONFIG = machine_config["file_structure"]

NORMAL_RAW_SUFFIXES = RAW_FILES_CONFIG["normal_raw_suffixes"]
STATISTICS_SUFFIX = RAW_FILES_CONFIG["statistics_suffix"]
ALLOW_STATISTICS_HOUR_DIFFERENCE = RAW_FILES_CONFIG[
    "allow_statistics_hour_difference"
]
STATISTICS_FOLDER_NAME = FILE_STRUCTURE_CONFIG["statistics_folder_name"]


def clean_filename_part(value: str | None) -> str:
    if value is None:
        return "unknown"

    value = str(value).strip()

    if value == "":
        return "unknown"

    value = re.sub(r'[<>:"/\\|?*#]', "_", value)
    value = value.replace(" ", "_")

    return value


def clean_device_name(device: str | None) -> str:
    if device is None:
        return "unknown"

    device = str(device).strip()

    if device == "":
        return "unknown"

    # Example:
    # VR-5200#BC910105 -> VR-5200
    device = device.split("#")[0]

    return clean_filename_part(device)


def build_export_base_name(cell_data: dict, group_key: str) -> str:
    product_name = clean_filename_part(cell_data.get("product_name"))
    cell_dmc = clean_filename_part(cell_data.get("cell_dmc"))
    device = clean_device_name(cell_data.get("device"))
    quality = clean_filename_part(cell_data.get("quality"))

    return f"{group_key}_{product_name}_{cell_dmc}_{device}_{quality}"


def find_source_file_in_group(cell_data: dict, file_group: list[Path]) -> Path:
    source_file_name = Path(cell_data["source_file"]).name

    for file_path in file_group:
        if file_path.name == source_file_name:
            return file_path

    return Path(cell_data["source_file"])


def build_expected_raw_file_names(source_stem: str) -> list[str]:
    return [
        f"{source_stem}{suffix}"
        for suffix in NORMAL_RAW_SUFFIXES
    ]


def find_statistics_file(source_file: Path) -> Path | None:
    """
    Finds the matching statistics file in:
    recipe_folder/Statistics/YYYYMMDD/

    For Keyence .zir files, the hour in the Statistics filename may differ.
    Therefore, if configured, we match by:
    - same date
    - same minute + second
    - same cell number
    - same device part
    """

    date_folder = source_file.parent
    recipe_output_folder = date_folder.parent
    statistics_date_folder = (
        recipe_output_folder
        / STATISTICS_FOLDER_NAME
        / date_folder.name
    )

    if not statistics_date_folder.is_dir():
        return None

    if not ALLOW_STATISTICS_HOUR_DIFFERENCE:
        exact_file = statistics_date_folder / f"{source_file.stem}{STATISTICS_SUFFIX}"

        if exact_file.is_file():
            return exact_file

        return None

    # Example:
    # 20260507_073049_001_VR-5200#7C020054
    parts = source_file.stem.split("_", maxsplit=3)

    if len(parts) != 4:
        return None

    source_date = parts[0]
    source_time = parts[1]
    source_cell_number = parts[2]
    source_device_part = parts[3]

    minute_second = source_time[2:]

    pattern = re.compile(
        rf"^{re.escape(source_date)}_\d{{2}}{re.escape(minute_second)}_"
        rf"{re.escape(source_cell_number)}_"
        rf"{re.escape(source_device_part)}"
        rf"{re.escape(STATISTICS_SUFFIX)}$",
        re.IGNORECASE,
    )

    matches = [
        file_path
        for file_path in statistics_date_folder.iterdir()
        if file_path.is_file() and pattern.match(file_path.name)
    ]

    if not matches:
        return None

    return sorted(matches)[0]


def has_configured_normal_raw_suffix(file_path: Path, source_stem: str) -> bool:
    expected_names = build_expected_raw_file_names(source_stem)
    return file_path.name in expected_names


def find_related_files(cell_data: dict, file_group: list[Path]) -> list[Path]:
    source_file = find_source_file_in_group(cell_data, file_group)
    source_stem = source_file.stem

    related_files = []

    for file_path in file_group:
        if not file_path.is_file():
            continue

        if has_configured_normal_raw_suffix(file_path, source_stem):
            related_files.append(file_path)

    statistics_file = find_statistics_file(source_file)

    if statistics_file is not None:
        related_files.append(statistics_file)

    return related_files


def find_missing_raw_files(cell_data: dict, file_group: list[Path]) -> list[str]:
    source_file = find_source_file_in_group(cell_data, file_group)
    source_stem = source_file.stem

    existing_names = {
        file_path.name
        for file_path in file_group
        if file_path.is_file()
    }

    expected_names = build_expected_raw_file_names(source_stem)

    missing_files = []

    for expected_name in expected_names:
        if expected_name not in existing_names:
            missing_files.append(expected_name)

    statistics_file = find_statistics_file(source_file)

    if statistics_file is None:
        missing_files.append(f"{source_stem}{STATISTICS_SUFFIX}")

    return missing_files


def print_missing_raw_files_warning(cell_data: dict, missing_files: list[str]) -> None:
    if not missing_files:
        return

    print(f"WARNING: Missing related raw files for {cell_data['cell_dmc']}:")

    for missing_file in missing_files:
        print(f"  - {missing_file}")


def export_related_files(
    cell_data: dict,
    file_group: list[Path],
    output_dir: Path,
    group_key: str
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    base_name = build_export_base_name(cell_data, group_key)
    related_files = find_related_files(cell_data, file_group)

    missing_files = find_missing_raw_files(cell_data, file_group)
    print_missing_raw_files_warning(cell_data, missing_files)

    exported_files = []

    source_file = find_source_file_in_group(cell_data, file_group)
    source_stem = source_file.stem

    for source_file in related_files:
        extra_suffix = ""

        # Keeps image suffixes like _h and _t.
        # Statistics files should become exactly {base_name}{STATISTICS_SUFFIX}.
        if source_file.suffix.lower() != STATISTICS_SUFFIX.lower():
            if source_file.stem.startswith(source_stem):
                extra_suffix = source_file.stem[len(source_stem):]

        target_file = output_dir / f"{base_name}{extra_suffix}{source_file.suffix}"

        shutil.copy2(source_file, target_file)
        exported_files.append(target_file)

    return exported_files