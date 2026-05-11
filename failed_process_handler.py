from pathlib import Path
import shutil


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


def move_failed_group(
    output_dir: Path,
    failed_process_dir: Path,
    group_key: str,
) -> list[Path]:
    """
    Moves all existing exported files of a failed group_key
    from data_lake_ready to failed_process.

    Example:
    group_key = 20260409_112101
    moves all files starting with 20260409_112101_
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
) -> list[Path]:
    """
    Copies all existing input files of a failed group to failed_process.

    Important:
    - This is used when the group is processed but failed.
    - Input cleanup may happen afterwards.
    - Existing files are copied; missing files are documented in the report.
    """

    failed_process_dir.mkdir(parents=True, exist_ok=True)

    copied_files = []

    for source_file in files:
        source_file = Path(source_file)

        if not source_file.is_file():
            continue

        target_file = failed_process_dir / source_file.name
        shutil.copy2(source_file, target_file)
        copied_files.append(target_file)

    return copied_files


def verify_failed_input_group_copy(
    files: list[Path],
    failed_process_dir: Path,
) -> list[dict]:
    """
    Verifies that all existing input files were copied to failed_process.
    """

    problems = []

    for source_file in files:
        source_file = Path(source_file)

        if not source_file.is_file():
            continue

        copied_file = failed_process_dir / source_file.name

        if not copied_file.exists():
            problems.append(
                {
                    "base": source_file.stem,
                    "problem": "copy_missing",
                    "details": copied_file.name,
                }
            )

    return problems