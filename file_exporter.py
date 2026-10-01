from pathlib import Path
import re
import shutil

from config_loader import machine_config


RAW_FILES_CONFIG = machine_config["raw_files"]
FILE_STRUCTURE_CONFIG = machine_config["file_structure"]
PREVIEW_CONFIG = machine_config.get("preview", {})

# Required files for the normal/template run.
# These are the only files that decide whether a raw cell is complete.
NORMAL_RAW_SUFFIXES = RAW_FILES_CONFIG["normal_raw_suffixes"]

# Optional artifacts.
# They are exported when present, but they are not required for success.
OPTIONAL_IMAGE_EXTENSIONS = [
    extension.lower()
    for extension in RAW_FILES_CONFIG.get(
        "optional_image_extensions",
        [
            ".png",
            ".jpg",
            ".jpeg",
            ".bmp",
            ".tif",
            ".tiff",
            ".webp",
        ],
    )
]

STATISTICS_SUFFIX = RAW_FILES_CONFIG["statistics_suffix"]
STATISTICS_REQUIRED = RAW_FILES_CONFIG.get("statistics_required", False)

ALLOW_STATISTICS_HOUR_DIFFERENCE = RAW_FILES_CONFIG[
    "allow_statistics_hour_difference"
]

DEVICE_SERIAL_SEPARATOR = RAW_FILES_CONFIG["device_serial_separator"]
STATISTICS_FOLDER_NAME = FILE_STRUCTURE_CONFIG["statistics_folder_name"]

PREVIEW_ENABLED = PREVIEW_CONFIG.get("enabled", True)
PREVIEW_WIDTH = PREVIEW_CONFIG.get("preview_width", 160)
PREVIEW_HEIGHT = PREVIEW_CONFIG.get("preview_height", 120)


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
    if DEVICE_SERIAL_SEPARATOR and DEVICE_SERIAL_SEPARATOR in device:
        device = device.split(DEVICE_SERIAL_SEPARATOR)[0]

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
    Finds the matching optional statistics file in:
    recipe_folder/Statistics/YYYYMMDD/

    For Keyence .zir files, the hour in the Statistics filename may differ.
    Therefore, if configured, we match by:
    - same date
    - same minute + second
    - same cell number
    - same device part

    Missing statistics files are allowed by default and do not fail the
    template run unless statistics_required = true is configured.
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


def has_required_raw_suffix(file_path: Path, source_stem: str) -> bool:
    expected_names = build_expected_raw_file_names(source_stem)
    return file_path.name in expected_names


def is_optional_image_file(file_path: Path) -> bool:
    return file_path.is_file() and file_path.suffix.lower() in OPTIONAL_IMAGE_EXTENSIONS


def source_stem_parts(source_stem: str) -> tuple[str, str, str] | None:
    """
    Returns date, time and cell/running number from a Keyence source stem.

    Example:
    20260507_073049_001_VR-5200#7C020054
    -> ("20260507", "073049", "001")
    """

    parts = source_stem.split("_", maxsplit=3)

    if len(parts) < 3:
        return None

    return parts[0], parts[1], parts[2]


def image_belongs_to_source(file_path: Path, source_stem: str) -> bool:
    """
    Checks whether an optional image belongs to a source file.

    Preferred case:
    - image stem starts with the full source stem
      e.g. source_h.png, source_t.jpg, source_3d.jpeg

    Fallback case:
    - image starts with the same date, time and running cell number
      e.g. 20260507_073049_001_anything.png

    This keeps image handling flexible without assigning completely unrelated
    image files to every cell in the group.
    """

    if not is_optional_image_file(file_path):
        return False

    if file_path.stem.startswith(source_stem):
        return True

    parts = source_stem_parts(source_stem)

    if parts is None:
        return False

    date, time, cell_number = parts
    source_prefix = f"{date}_{time}_{cell_number}_"

    return file_path.stem.startswith(source_prefix)


def get_image_extra_suffix(
    image_file: Path,
    source_stem: str,
    image_number: int,
) -> str:
    """
    Builds the unified suffix for an exported optional image.

    If the source image already has a meaningful suffix after the source stem,
    it is preserved:
    source_h.png  -> base_h.png
    source_t.jpg  -> base_t.jpg
    source_3d.jpg -> base_3d.jpg

    If the image does not follow that pattern, a stable generic suffix is used:
    base_image_01.png
    """

    if image_file.stem.startswith(source_stem):
        extra_suffix = image_file.stem[len(source_stem):]

        if extra_suffix:
            return clean_filename_part(extra_suffix).replace("unknown", f"image_{image_number:02d}")

    return f"_image_{image_number:02d}"


def get_related_optional_image_files(
    source_file: Path,
    file_group: list[Path],
) -> list[Path]:
    source_stem = source_file.stem

    image_files = [
        file_path
        for file_path in file_group
        if image_belongs_to_source(
            file_path=file_path,
            source_stem=source_stem,
        )
    ]

    return sorted(
        image_files,
        key=lambda path: path.name.lower(),
    )


def has_configured_normal_raw_suffix(file_path: Path, source_stem: str) -> bool:
    """
    Backwards-compatible name used by older code paths.

    It now checks only the required normal/template raw files, not optional
    images and not optional statistics files.
    """

    return has_required_raw_suffix(file_path, source_stem)


def get_source_stem_from_raw_file(file_path: Path) -> str | None:
    """
    Detects the original source stem from one required normal raw file.

    Examples:
    example.xlsx -> example
    example.csv  -> example
    example.zmr  -> example

    Optional image files are intentionally not used for source-stem detection.
    They are attached to detected source stems later.
    """

    for suffix in sorted(NORMAL_RAW_SUFFIXES, key=len, reverse=True):
        if file_path.name.endswith(suffix):
            return file_path.name[:-len(suffix)]

    return None


def find_source_stems_in_group(file_group: list[Path]) -> list[str]:
    source_stems = set()

    for file_path in file_group:
        if not file_path.is_file():
            continue

        source_stem = get_source_stem_from_raw_file(file_path)

        if source_stem is not None:
            source_stems.add(source_stem)

    return sorted(source_stems)


def get_existing_statistics_files_for_group(file_group: list[Path]) -> list[Path]:
    """
    Finds existing optional statistics files for all detected source stems.
    """

    statistics_files = []
    source_stems = find_source_stems_in_group(file_group)

    if not file_group:
        return statistics_files

    date_folder = Path(file_group[0]).parent

    for source_stem in source_stems:
        pseudo_source_file = date_folder / f"{source_stem}.xlsx"
        statistics_file = find_statistics_file(pseudo_source_file)

        if statistics_file is not None:
            statistics_files.append(statistics_file)

    return statistics_files


def get_available_raw_files_for_failed_group(file_group: list[Path]) -> list[Path]:
    """
    Returns existing group files plus existing optional statistics files.

    Used when a failed group must be copied to failed_process.
    Optional files are retained when they are available, but they are not
    required for a successful analytical run.
    """

    available_files = [
        file_path
        for file_path in file_group
        if file_path.is_file()
    ]

    available_files.extend(
        get_existing_statistics_files_for_group(file_group)
    )

    unique_files = []
    seen_paths = set()

    for file_path in available_files:
        resolved_path = Path(file_path).resolve()

        if resolved_path in seen_paths:
            continue

        seen_paths.add(resolved_path)
        unique_files.append(Path(file_path))

    return unique_files


def verify_raw_group_completeness(file_group: list[Path]) -> list[dict]:
    """
    Verifies that every dynamically detected cell/source stem has all required
    template-run raw files.

    Important:
    - Does not assume a fixed number of cells.
    - 8 cells, 12 cells or 20 cells are all valid if each detected cell is complete.
    - Checks only required normal raw files.
    - Optional images and optional statistics files never fail this check.
    """

    problems = []
    source_stems = find_source_stems_in_group(file_group)

    if not source_stems:
        problems.append(
            {
                "base": "unknown",
                "missing_files": ["No source files detected in group"],
            }
        )

        return problems

    existing_names = {
        file_path.name
        for file_path in file_group
        if file_path.is_file()
    }

    for source_stem in source_stems:
        missing_files = []

        expected_names = build_expected_raw_file_names(source_stem)

        for expected_name in expected_names:
            if expected_name not in existing_names:
                missing_files.append(expected_name)

        if STATISTICS_REQUIRED:
            date_folder = Path(file_group[0]).parent
            pseudo_source_file = date_folder / f"{source_stem}.xlsx"
            statistics_file = find_statistics_file(pseudo_source_file)

            if statistics_file is None:
                missing_files.append(f"{source_stem}{STATISTICS_SUFFIX}")

        if missing_files:
            problems.append(
                {
                    "base": source_stem,
                    "missing_files": missing_files,
                }
            )

    return problems


def find_related_files(cell_data: dict, file_group: list[Path]) -> list[Path]:
    """
    Finds all files that belong to a cell/source stem.

    Required:
    - configured normal template files (.xlsx, .csv, .zmr)

    Optional:
    - any matching image file with a configured image extension
    - matching statistics file, if it exists
    """

    source_file = find_source_file_in_group(cell_data, file_group)
    source_stem = source_file.stem

    related_files = []

    for file_path in file_group:
        if not file_path.is_file():
            continue

        if has_required_raw_suffix(file_path, source_stem):
            related_files.append(file_path)

    related_files.extend(
        get_related_optional_image_files(
            source_file=source_file,
            file_group=file_group,
        )
    )

    statistics_file = find_statistics_file(source_file)

    if statistics_file is not None:
        related_files.append(statistics_file)

    unique_files = []
    seen_paths = set()

    for file_path in related_files:
        resolved_path = Path(file_path).resolve()

        if resolved_path in seen_paths:
            continue

        seen_paths.add(resolved_path)
        unique_files.append(file_path)

    return unique_files


def find_missing_raw_files(cell_data: dict, file_group: list[Path]) -> list[str]:
    """
    Returns missing required raw files for a cell.

    Optional images and optional statistics files are not returned as missing
    unless statistics_required = true is configured.
    """

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

    if STATISTICS_REQUIRED:
        statistics_file = find_statistics_file(source_file)

        if statistics_file is None:
            missing_files.append(f"{source_stem}{STATISTICS_SUFFIX}")

    return missing_files


def print_missing_raw_files_warning(cell_data: dict, missing_files: list[str]) -> None:
    if not missing_files:
        return

    print(f"WARNING: Missing required raw files for {cell_data['cell_dmc']}:")

    for missing_file in missing_files:
        print(f"  - {missing_file}")


def create_preview_for_image(
    image_path: Path,
    preview_path: Path,
) -> Path | None:
    """
    Creates a preview for one exported image.

    Preview generation is optional. If the image cannot be opened, the wrapper
    prints a warning and continues. The export itself still succeeds because
    images are optional artifacts.
    """

    if not PREVIEW_ENABLED:
        return None

    if preview_path.exists():
        return preview_path

    try:
        from PIL import Image
    except ImportError:
        print(
            "WARNING: Pillow is not installed. "
            f"Could not create preview for {image_path.name}."
        )
        return None

    try:
        with Image.open(image_path) as image:
            image.thumbnail((PREVIEW_WIDTH, PREVIEW_HEIGHT))
            preview = image.copy()

            if preview.mode not in ("RGB", "RGBA"):
                preview = preview.convert("RGB")

            preview_path.parent.mkdir(parents=True, exist_ok=True)
            preview.save(preview_path)

        return preview_path

    except Exception as error:
        print(
            f"WARNING: Could not create preview for {image_path.name}: "
            f"{type(error).__name__}: {error}"
        )

        return None


def build_preview_path_for_exported_image(exported_image_path: Path) -> Path:
    """
    Creates the preview filename for an exported image.

    Example:
    base_h.jpg       -> base_h_preview.png
    base_image_01.png -> base_image_01_preview.png
    """

    return (
        exported_image_path.parent
        / f"{exported_image_path.stem}_preview.png"
    )


def build_target_file_for_related_source(
    source_file: Path,
    output_dir: Path,
    base_name: str,
    source_stem: str,
    image_number: int,
) -> Path:
    if source_file.suffix.lower() == STATISTICS_SUFFIX.lower():
        return output_dir / f"{base_name}{STATISTICS_SUFFIX}"

    if is_optional_image_file(source_file):
        extra_suffix = get_image_extra_suffix(
            image_file=source_file,
            source_stem=source_stem,
            image_number=image_number,
        )

        return output_dir / f"{base_name}{extra_suffix}{source_file.suffix.lower()}"

    return output_dir / f"{base_name}{source_file.suffix}"


def export_related_files(
    cell_data: dict,
    file_group: list[Path],
    output_dir: Path,
    group_key: str,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    base_name = build_export_base_name(cell_data, group_key)
    related_files = find_related_files(cell_data, file_group)

    missing_files = find_missing_raw_files(cell_data, file_group)
    print_missing_raw_files_warning(cell_data, missing_files)

    exported_files = []

    source_anchor_file = find_source_file_in_group(cell_data, file_group)
    source_stem = source_anchor_file.stem
    image_number = 0

    for source_file in related_files:
        if is_optional_image_file(source_file):
            image_number += 1

        target_file = build_target_file_for_related_source(
            source_file=source_file,
            output_dir=output_dir,
            base_name=base_name,
            source_stem=source_stem,
            image_number=image_number,
        )

        shutil.copy2(source_file, target_file)
        exported_files.append(target_file)

        if is_optional_image_file(source_file):
            preview_path = build_preview_path_for_exported_image(target_file)
            created_preview = create_preview_for_image(
                image_path=target_file,
                preview_path=preview_path,
            )

            if created_preview is not None:
                exported_files.append(created_preview)

    return exported_files
