from pathlib import Path
import shutil

from extractor import extract_metadata, normalize_positions, determine_quality
from file_exporter import (
    build_export_base_name,
    find_related_files,
    find_source_file_in_group,
)
from config_loader import machine_config


RAW_FILES_CONFIG = machine_config["raw_files"]
STATISTICS_SUFFIX = RAW_FILES_CONFIG["statistics_suffix"]

MISSING_DMC_PLACEHOLDER = "MISSING_DMC"


def build_invalid_cell_data_list(files: list[Path]) -> list[dict]:
    metadata_list = extract_metadata(files)
    position_mapping = normalize_positions(metadata_list)

    cell_data_list = []

    for metadata in metadata_list:
        normalized_position = position_mapping[metadata.position]
        leadframe_dmc = metadata.leadframe_dmc or MISSING_DMC_PLACEHOLDER
        cell_dmc = f"{leadframe_dmc}-{normalized_position}"

        cell_data = {
            "source_file": metadata.source_file,
            "timestamp": metadata.timestamp,
            "leadframe_dmc": leadframe_dmc,
            "raw_position": metadata.position,
            "position": normalized_position,
            "cell_dmc": cell_dmc,
            "name": metadata.name,
            "product_name": metadata.product_name,
            "device": metadata.device,
            "overall_result": metadata.overall_result,
            "quality": determine_quality(metadata),
        }

        cell_data_list.append(cell_data)

    return cell_data_list


def copy_related_files_with_standardized_names(
    cell_data: dict,
    files: list[Path],
    target_dir: Path,
    group_key: str,
) -> list[Path]:
    target_dir.mkdir(parents=True, exist_ok=True)

    copied_files = []

    base_name = build_export_base_name(cell_data, group_key)
    source_file = find_source_file_in_group(cell_data, files)
    source_stem = source_file.stem

    related_files = find_related_files(cell_data, files)

    for related_file in related_files:
        extra_suffix = ""

        if related_file.suffix.lower() != STATISTICS_SUFFIX.lower():
            if related_file.stem.startswith(source_stem):
                extra_suffix = related_file.stem[len(source_stem):]

        target_file = target_dir / f"{base_name}{extra_suffix}{related_file.suffix}"

        shutil.copy2(related_file, target_file)
        copied_files.append(target_file)

    return copied_files


def copy_invalid_group(
    files: list[Path],
    no_dmc_dir: Path,
    group_key: str,
) -> list[Path]:
    copied_files: list[Path] = []

    cell_data_list = build_invalid_cell_data_list(files)

    copied_source_names = set()

    for cell_data in cell_data_list:
        related_files = find_related_files(cell_data, files)

        for related_file in related_files:
            copied_source_names.add(related_file.name)

        copied_files.extend(
            copy_related_files_with_standardized_names(
                cell_data=cell_data,
                files=files,
                target_dir=no_dmc_dir,
                group_key=group_key,
            )
        )

    # Fallback: copy files that could not be assigned to an Excel-based cell.
    for source_file in files:
        source_file = Path(source_file)

        if not source_file.is_file():
            continue

        if source_file.name in copied_source_names:
            continue

        target_file = no_dmc_dir / f"{group_key}_UNSTANDARDIZED_{source_file.name}"
        shutil.copy2(source_file, target_file)
        copied_files.append(target_file)

    return copied_files


def verify_invalid_group_copy(
    files: list[Path],
    no_dmc_dir: Path,
    group_key: str,
) -> list[dict]:
    problems: list[dict] = []

    copied_files = list(no_dmc_dir.glob(f"{group_key}_*"))

    if not copied_files:
        problems.append(
            {
                "type": "missing_copied_files",
                "source": "invalid group",
                "expected_target": str(no_dmc_dir / f"{group_key}_*"),
            }
        )

    return problems


def write_invalid_group_report(
    no_dmc_dir: Path,
    group_key: str,
    reason: str,
    problems: list[dict] | None = None,
) -> Path:
    report_path = no_dmc_dir / f"{group_key}_INVALID_REPORT.txt"

    lines = [
        "INVALID GROUP REPORT",
        "",
        f"group_key: {group_key}",
        f"reason: {reason}",
        "",
    ]

    if problems:
        lines.append("copy problems:")
        for problem in problems:
            lines.append(f"- type: {problem.get('type')}")
            lines.append(f"  source: {problem.get('source')}")
            lines.append(f"  expected_target: {problem.get('expected_target')}")
    else:
        lines.append("copy verification: OK")

    report_path.write_text("\n".join(lines), encoding="utf-8")

    return report_path