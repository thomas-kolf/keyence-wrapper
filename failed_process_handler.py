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


def write_failure_report(
    failed_process_dir: Path,
    group_key: str,
    verification_type: str,
    problems: list[dict],
) -> Path:
    failed_process_dir.mkdir(parents=True, exist_ok=True)

    report_path = failed_process_dir / f"{group_key}_FAILURE_REPORT.txt"

    with report_path.open("a", encoding="utf-8") as file:
        file.write("=" * 80 + "\n")
        file.write(f"Group: {group_key}\n")
        file.write(f"Verification: {verification_type}\n")
        file.write("=" * 80 + "\n\n")

        for problem in problems:
            file.write(f"Base: {problem.get('base')}\n")

            if "missing_files" in problem:
                file.write("Missing files:\n")
                for missing_file in problem["missing_files"]:
                    file.write(f"  - {missing_file}\n")

            elif problem.get("problem") == "missing_csv":
                file.write("Problem: missing_csv\n")
                file.write(f"Missing CSV: {problem.get('details')}\n")

            elif problem.get("problem") == "measurement_count_mismatch":
                file.write("Problem: measurement_count_mismatch\n")
                file.write(f"JSON count: {problem.get('json_count')}\n")
                file.write(f"CSV count: {problem.get('csv_count')}\n")

            elif problem.get("problem") == "value_mismatch":
                file.write("Problem: value_mismatch\n")
                file.write(f"Row: {problem.get('row')}\n")
                file.write(f"Field: {problem.get('field')}\n")
                file.write(f"JSON value: {problem.get('json_value')}\n")
                file.write(f"CSV value: {problem.get('csv_value')}\n")

            elif problem.get("problem") == "copy_missing":
                file.write("Problem: copy_missing\n")
                file.write(f"Missing copied file: {problem.get('details')}\n")

            file.write("\n")

    return report_path


def build_failed_cell_data_list(files: list[Path]) -> list[dict]:
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


def move_failed_group(
    output_dir: Path,
    failed_process_dir: Path,
    group_key: str,
) -> list[Path]:
    """
    Moves all existing standardized exported files of a failed group_key
    from data_lake_ready to failed_process.
    """

    failed_process_dir.mkdir(parents=True, exist_ok=True)

    moved_files = []

    matching_files = list(output_dir.glob(f"{group_key}_*"))

    for source_file in matching_files:
        target_file = failed_process_dir / source_file.name

        shutil.move(str(source_file), str(target_file))
        moved_files.append(target_file)

    return moved_files


def copy_failed_input_group(
    files: list[Path],
    failed_process_dir: Path,
    group_key: str,
) -> list[Path]:
    """
    Copies existing input files of a failed group to failed_process
    using the standardized wrapper naming where possible.
    """

    failed_process_dir.mkdir(parents=True, exist_ok=True)

    copied_files = []
    copied_source_names = set()

    cell_data_list = build_failed_cell_data_list(files)

    for cell_data in cell_data_list:
        related_files = find_related_files(cell_data, files)

        for related_file in related_files:
            copied_source_names.add(related_file.name)

        copied_files.extend(
            copy_related_files_with_standardized_names(
                cell_data=cell_data,
                files=files,
                target_dir=failed_process_dir,
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

        target_file = failed_process_dir / f"{group_key}_UNSTANDARDIZED_{source_file.name}"
        shutil.copy2(source_file, target_file)
        copied_files.append(target_file)

    return copied_files


def verify_failed_input_group_copy(
    files: list[Path],
    failed_process_dir: Path,
    group_key: str,
) -> list[dict]:
    """
    Verifies that failed_process received files for the group.
    """

    problems = []

    copied_files = list(failed_process_dir.glob(f"{group_key}_*"))

    if not copied_files:
        problems.append(
            {
                "base": group_key,
                "problem": "copy_missing",
                "details": f"No files copied for {group_key}",
            }
        )

    return problems