from pathlib import Path
import shutil


def move_failed_exports(
    output_dir: Path,
    failed_process_dir: Path,
    problems: list[dict],
) -> list[Path]:
    """
    Moves all existing exported files for failed bases from data_lake_ready
    into failed_process.

    Important:
    - input files are not touched
    - only already-created output files are moved
    """

    failed_process_dir.mkdir(parents=True, exist_ok=True)

    moved_files = []

    failed_bases = {problem["base"] for problem in problems}

    for base in failed_bases:
        matching_files = list(output_dir.glob(f"{base}*"))

        for source_file in matching_files:
            target_file = failed_process_dir / source_file.name

            shutil.move(str(source_file), str(target_file))
            moved_files.append(target_file)

    return moved_files