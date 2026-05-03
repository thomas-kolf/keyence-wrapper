from pathlib import Path
import shutil
import re


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


def find_related_files(cell_data: dict, file_group: list[Path]) -> list[Path]:
    source_file = Path(cell_data["source_file"])
    source_stem = source_file.stem

    related_files = []

    for file_path in file_group:
        if not file_path.is_file():
            continue

        # Same base name:
        # example.xlsx, example.csv, example.zmr
        if file_path.stem == source_stem:
            related_files.append(file_path)
            continue

        # Additional files:
        # example_h.png, example_t.png
        if file_path.stem.startswith(source_stem + "_"):
            related_files.append(file_path)

    return related_files


def export_related_files(
    cell_data: dict,
    file_group: list[Path],
    output_dir: Path,
    group_key: str
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    base_name = build_export_base_name(cell_data, group_key)
    related_files = find_related_files(cell_data, file_group)

    exported_files = []

    source_stem = Path(cell_data["source_file"]).stem

    for source_file in related_files:
        extra_suffix = ""

        # Keeps image suffixes like _h and _t
        if source_file.stem.startswith(source_stem):
            extra_suffix = source_file.stem[len(source_stem):]

        target_file = output_dir / f"{base_name}{extra_suffix}{source_file.suffix}"

        shutil.copy2(source_file, target_file)
        exported_files.append(target_file)

    return exported_files