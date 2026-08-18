from pathlib import Path
import shutil
import sys
from datetime import datetime

from config_loader import machine_config

from file_grouping import find_file_groups
from extractor import build_cell_data, write_cell_json
from file_exporter import (
    export_related_files,
    build_export_base_name,
    verify_raw_group_completeness,
    find_missing_raw_files,
    find_related_files,
    find_statistics_file,
    get_source_stem_from_raw_file,
    find_source_stems_in_group,
)
from powerbi_csv_creator import create_powerbi_csv_from_json
from excel_image_embedder import embed_h_image_in_excel
from preview_generator import generate_previews
from export_verifier import verify_exports, print_export_verification_result
from measurement_verifier import (
    verify_measurements,
    print_measurement_verification_result,
)
from failed_process_handler import (
    write_failure_report,
    copy_related_files_with_standardized_names,
)
from input_cleanup import (
    cleanup_processed_group,
    cleanup_empty_date_folders,
    move_statistics_folders_to_input_root,
    cleanup_empty_recipe_output_folders,
)
from invalid_group_handler import write_invalid_group_report


PREVIEW_ENABLED = machine_config["preview"]["enabled"]

RUNTIME_PATHS = machine_config.get("runtime_paths", {})

INPUT_DIR = Path(
    RUNTIME_PATHS.get(
        "input_dir",
        "input",
    )
)

STANDARDIZED_OUTPUT_ROOT_DIR = Path(
    RUNTIME_PATHS.get(
        "standardized_output_root_dir",
        "data_lake_ready",
    )
)

POWERBI_DETAILS_DIR = Path(
    RUNTIME_PATHS.get(
        "powerbi_details_dir",
        "Powerbi_Details",
    )
)

LOGS_DIR = Path(
    RUNTIME_PATHS.get(
        "logs_dir",
        "Logs",
    )
)


class TeeLogger:
    """
    Writes console output to both terminal and log file.
    """

    def __init__(self, *streams):
        self.streams = streams

    def write(self, message: str) -> None:
        for stream in self.streams:
            stream.write(message)
            stream.flush()

    def flush(self) -> None:
        for stream in self.streams:
            stream.flush()


def normalize_missing_dmc_for_output(cell_data: dict) -> dict:
    """
    Missing DMC is no longer a technical failure.
    Only the affected cell gets MISSING_DMC-XX.
    """

    if not cell_data.get("leadframe_dmc"):
        cell_data["leadframe_dmc"] = None
        cell_data["cell_dmc"] = f"MISSING_DMC-{cell_data['position']}"

    return cell_data


def unique_paths(paths: list[Path]) -> list[Path]:
    unique = []
    seen = set()

    for path in paths:
        resolved_path = Path(path).resolve()

        if resolved_path in seen:
            continue

        seen.add(resolved_path)
        unique.append(Path(path))

    return unique


def align_cell_positions_to_source_stems(
    cell_data_list: list[dict],
    files: list[Path],
) -> list[dict]:
    """
    Keeps positions stable even if one Excel file is missing.
    """

    source_stems = find_source_stems_in_group(files)

    position_by_source_stem = {
        source_stem: f"{index:02d}"
        for index, source_stem in enumerate(source_stems, start=1)
    }

    for cell_data in cell_data_list:
        source_stem = Path(cell_data["source_file"]).stem
        corrected_position = position_by_source_stem.get(source_stem)

        if corrected_position is None:
            continue

        old_position = cell_data.get("position")
        cell_data["position"] = corrected_position

        leadframe_dmc = cell_data.get("leadframe_dmc")

        if leadframe_dmc:
            cell_data["cell_dmc"] = f"{leadframe_dmc}-{corrected_position}"
        else:
            cell_data["cell_dmc"] = f"MISSING_DMC-{corrected_position}"

        if old_position != corrected_position:
            print(
                f"Position corrected for {source_stem}: "
                f"{old_position} -> {corrected_position}"
            )

    return cell_data_list


def write_json_and_powerbi_csv_output(
    cell_data: dict,
    output_dir: Path,
    group_key: str,
) -> tuple[Path, Path]:
    normalize_missing_dmc_for_output(cell_data)

    file_base_name = build_export_base_name(
        cell_data,
        group_key,
    )

    json_file = write_cell_json(
        cell_data=cell_data,
        output_dir=output_dir,
        file_base_name=file_base_name,
    )

    powerbi_csv_file = create_powerbi_csv_from_json(
        json_file
    )

    return json_file, powerbi_csv_file


def copy_incomplete_cell_to_input(
    cell_data: dict,
    files: list[Path],
    input_dir: Path,
    group_key: str,
) -> list[Path]:
    """
    Copies existing files of one incomplete cell flat to the machine root.
    Uses standardized naming where possible.
    """

    normalize_missing_dmc_for_output(
        cell_data
    )

    return copy_related_files_with_standardized_names(
        cell_data=cell_data,
        files=files,
        target_dir=input_dir,
        group_key=group_key,
    )


def move_output_files_for_base(
    output_dir: Path,
    target_dir: Path,
    base_name: str,
) -> list[Path]:
    """
    Moves already exported files for one failed exported cell base
    from the standardized recipe folder to the machine root.
    """

    target_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    moved_files = []

    for source_file in output_dir.glob(
        f"{base_name}*"
    ):
        if not source_file.is_file():
            continue

        target_file = (
            target_dir
            / source_file.name
        )

        if target_file.exists():
            target_file.unlink()

        shutil.move(
            str(source_file),
            str(target_file),
        )

        moved_files.append(
            target_file
        )

    return moved_files


def get_existing_files_for_unassigned_source_stem(
    files: list[Path],
    source_stem: str,
) -> list[Path]:
    """
    Handles the edge case where raw files exist for a cell,
    but no Excel file exists, so no cell_data can be built.
    """

    existing_files = []

    for file_path in files:
        if not file_path.is_file():
            continue

        detected_stem = get_source_stem_from_raw_file(
            file_path
        )

        if detected_stem == source_stem:
            existing_files.append(
                file_path
            )

    if files:
        date_folder = Path(
            files[0]
        ).parent

        pseudo_source_file = (
            date_folder
            / f"{source_stem}.xlsx"
        )

        statistics_file = find_statistics_file(
            pseudo_source_file
        )

        if statistics_file is not None:
            existing_files.append(
                statistics_file
            )

    return unique_paths(
        existing_files
    )


def copy_unassigned_failed_files_to_input(
    files: list[Path],
    input_dir: Path,
    group_key: str,
    source_stem: str,
) -> list[Path]:
    """
    Copies failed files that cannot be assigned to a cell_data object
    flat to the machine root.

    Example:
    Excel is missing, but CSV, images or ZMR files exist.
    """

    copied_files = []

    input_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    source_files = (
        get_existing_files_for_unassigned_source_stem(
            files=files,
            source_stem=source_stem,
        )
    )

    for source_file in source_files:
        target_file = (
            input_dir
            / f"{group_key}_UNSTANDARDIZED_{source_file.name}"
        )

        if target_file.exists():
            target_file.unlink()

        shutil.copy2(
            source_file,
            target_file,
        )

        copied_files.append(
            target_file
        )

    return copied_files


def move_powerbi_csv_files_to_details(
    recipe_output_dir: Path,
    powerbi_details_dir: Path,
    group_key: str,
) -> list[Path]:
    """
    Moves Power BI detail CSV files out of the standardized recipe folder
    after successful checks.

    Source:
    <machine_root>/<recipe_name>/*_PowerBI.csv

    Target:
    <machine_root>/Powerbi_Details/*_PowerBI.csv
    """

    powerbi_details_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    moved_files = []

    for source_file in recipe_output_dir.glob(
        f"{group_key}_*_PowerBI.csv"
    ):
        if not source_file.is_file():
            continue

        target_file = (
            powerbi_details_dir
            / source_file.name
        )

        if target_file.exists():
            target_file.unlink()

        shutil.move(
            str(source_file),
            str(target_file),
        )

        moved_files.append(
            target_file
        )

    return moved_files

def get_powerbi_details_dir_for_recipe(
    recipe_name: str,
) -> Path:
    """
    Returns the analytical Power BI output folder for a recipe.

    Default:
    existing Emb_Gan workflow remains V:/Powerbi_Details.

    Future products can be routed through [powerbi_details_rules]
    in machine_config.toml.
    """

    powerbi_details_rules = machine_config.get(
        "powerbi_details_rules",
        {},
    )

    configured_target = powerbi_details_rules.get(
        recipe_name
    )

    if configured_target:
        return Path(
            configured_target
        )

    return POWERBI_DETAILS_DIR

def run_pipeline() -> None:
    """
    Processes the machine folder directly.

    Expected machine root:
    V:/

    Incoming structure:
    V:/
    ├── random files
    ├── <recipe>.zit
    └── <recipe>_zit/
        ├── <YYYYMMDD>/
        └── Statistics/
            └── <YYYYMMDD>/

    Final structure:
    V:/
    ├── random files
    ├── failed or unprocessable files
    ├── <recipe>.zit
    ├── Statistics/
    │   └── <YYYYMMDD>/
    ├── Logs/
    │   └── <YYYYMMDD>/
    ├── Powerbi_Details/
    └── <recipe>_zit/
        └── standardized artifacts
    """

    input_dir = INPUT_DIR
    output_root_dir = (
        STANDARDIZED_OUTPUT_ROOT_DIR
    )

    input_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_root_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    POWERBI_DETAILS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    LOGS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    groups = find_file_groups(
        input_dir
    )

    print(
        f"Found groups: "
        f"{len(groups)}"
    )

    if not groups:
        print(
            "No input groups found. "
            "Nothing to process."
        )

        return

    for internal_group_id, group_info in groups.items():
        recipe_name = (
            group_info["recipe_name"]
        )

        group_key = (
            group_info["group_key"]
        )

        files = (
            group_info["files"]
        )

        date_folder_name = (
            group_key[:8]
        )

        group_logs_dir = (
            LOGS_DIR
            / date_folder_name
        )

        group_logs_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        recipe_output_dir = (
            output_root_dir
            / recipe_name
        )

        recipe_output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        print(
            f"\n{recipe_name} | "
            f"{group_key}: START"
        )

        raw_problems = (
            verify_raw_group_completeness(
                files
            )
        )

        try:
            cell_data_list = (
                build_cell_data(
                    files
                )
            )

            cell_data_list = (
                align_cell_positions_to_source_stems(
                    cell_data_list=cell_data_list,
                    files=files,
                )
            )

        except Exception as error:
            print(
                f"{recipe_name} | "
                f"{group_key}: FAILED | "
                f"Could not build cell data: "
                f"{type(error).__name__}: "
                f"{error}"
            )

            problems = raw_problems or [
                {
                    "base": group_key,
                    "missing_files": [
                        (
                            "Could not build cell data: "
                            f"{type(error).__name__}: "
                            f"{error}"
                        )
                    ],
                }
            ]

            report_path = write_failure_report(
                failed_process_dir=group_logs_dir,
                group_key=group_key,
                verification_type=(
                    "Cell data creation failed"
                ),
                problems=problems,
            )

            print(
                f"Failure report written: "
                f"{report_path.name}"
            )

            continue

        complete_cells = []
        incomplete_cells = []
        processed_input_files = []

        cell_source_stems = set()

        for cell_data in cell_data_list:
            normalize_missing_dmc_for_output(
                cell_data
            )

            source_file = Path(
                cell_data["source_file"]
            )

            cell_source_stems.add(
                source_file.stem
            )

            missing_files = find_missing_raw_files(
                cell_data,
                files,
            )

            if missing_files:
                incomplete_cells.append(
                    {
                        "cell_data": cell_data,
                        "missing_files": missing_files,
                    }
                )

            else:
                complete_cells.append(
                    cell_data
                )

        unassigned_raw_problems = []

        for problem in raw_problems:
            source_stem = problem.get(
                "base"
            )

            if source_stem not in cell_source_stems:
                unassigned_raw_problems.append(
                    problem
                )

        if complete_cells:
            print(
                f"{recipe_name} | "
                f"{group_key}: "
                f"complete cells = "
                f"{len(complete_cells)}"
            )

        if (
            incomplete_cells
            or unassigned_raw_problems
        ):
            failure_problems = []

            for incomplete_cell in incomplete_cells:
                cell_data = (
                    incomplete_cell[
                        "cell_data"
                    ]
                )

                source_file = Path(
                    cell_data[
                        "source_file"
                    ]
                )

                failure_problems.append(
                    {
                        "base": source_file.stem,
                        "missing_files": (
                            incomplete_cell[
                                "missing_files"
                            ]
                        ),
                    }
                )

            failure_problems.extend(
                unassigned_raw_problems
            )

            report_path = write_failure_report(
                failed_process_dir=group_logs_dir,
                group_key=group_key,
                verification_type=(
                    "Cell-level raw input "
                    "completeness failed"
                ),
                problems=failure_problems,
            )

            print(
                f"Failure report written: "
                f"{report_path.name}"
            )

        for incomplete_cell in incomplete_cells:
            cell_data = (
                incomplete_cell[
                    "cell_data"
                ]
            )

            copied_files = (
                copy_incomplete_cell_to_input(
                    cell_data=cell_data,
                    files=files,
                    input_dir=input_dir,
                    group_key=group_key,
                )
            )

            related_input_files = (
                find_related_files(
                    cell_data,
                    files,
                )
            )

            processed_input_files.extend(
                related_input_files
            )

            print(
                f"{cell_data['cell_dmc']} | "
                f"INCOMPLETE | "
                f"copied flat to machine root | "
                f"files={len(copied_files)}"
            )

        for problem in unassigned_raw_problems:
            source_stem = problem.get(
                "base"
            )

            copied_files = (
                copy_unassigned_failed_files_to_input(
                    files=files,
                    input_dir=input_dir,
                    group_key=group_key,
                    source_stem=source_stem,
                )
            )

            source_files = (
                get_existing_files_for_unassigned_source_stem(
                    files=files,
                    source_stem=source_stem,
                )
            )

            processed_input_files.extend(
                source_files
            )

            print(
                f"{source_stem} | "
                f"INCOMPLETE_UNASSIGNED | "
                f"copied flat to machine root | "
                f"files={len(copied_files)}"
            )

        if not complete_cells:
            deleted_files = (
                cleanup_processed_group(
                    unique_paths(
                        processed_input_files
                    )
                )
            )

            print(
                f"{recipe_name} | "
                f"{group_key}: "
                f"no complete cells exported | "
                f"deleted processed input files="
                f"{len(deleted_files)}"
            )

            continue

        missing_dmc_cells = [
            cell_data
            for cell_data in complete_cells
            if not cell_data.get(
                "leadframe_dmc"
            )
        ]

        if missing_dmc_cells:
            report_path = (
                write_invalid_group_report(
                    no_dmc_dir=group_logs_dir,
                    group_key=group_key,
                    reason=(
                        "Missing DMC in one or more "
                        "complete cells. "
                        "Cells were exported with "
                        "MISSING_DMC-XX naming."
                    ),
                )
            )

            print(
                f"Invalid report written: "
                f"{report_path.name}"
            )

        for cell_data in complete_cells:
            file_base_name = (
                build_export_base_name(
                    cell_data,
                    group_key,
                )
            )

            (
                output_file,
                powerbi_csv_file,
            ) = (
                write_json_and_powerbi_csv_output(
                    cell_data=cell_data,
                    output_dir=recipe_output_dir,
                    group_key=group_key,
                )
            )

            exported_files = (
                export_related_files(
                    cell_data=cell_data,
                    file_group=files,
                    output_dir=recipe_output_dir,
                    group_key=group_key,
                )
            )

            embedded_excel = (
                embed_h_image_in_excel(
                    output_dir=recipe_output_dir,
                    file_base_name=file_base_name,
                )
            )

            related_input_files = (
                find_related_files(
                    cell_data,
                    files,
                )
            )

            processed_input_files.extend(
                related_input_files
            )

            if embedded_excel is not None:
                image_status = (
                    "image=embedded"
                )

            else:
                image_status = (
                    "image=not_embedded"
                )

            print(
                f"{cell_data['cell_dmc']} | "
                f"quality={cell_data['quality']} | "
                f"measurements="
                f"{len(cell_data['measurements'])} | "
                f"JSON={output_file.name} | "
                f"PowerBI_CSV="
                f"{powerbi_csv_file.name} | "
                f"files={len(exported_files)} | "
                f"{image_status}"
            )

        if PREVIEW_ENABLED:
            created_previews = (
                generate_previews(
                    recipe_output_dir
                )
            )

            group_previews = [
                preview
                for preview in created_previews
                if preview.name.startswith(
                    group_key
                )
            ]

            if group_previews:
                print(
                    f"Previews created for "
                    f"{group_key}: "
                    f"{len(group_previews)}"
                )

            else:
                print(
                    f"No new previews needed "
                    f"for {group_key}"
                )

        else:
            print(
                f"Preview generation disabled "
                f"for {group_key}"
            )

        export_problems = verify_exports(
            recipe_output_dir,
            group_key,
        )

        print_export_verification_result(
            export_problems,
            group_key,
        )

        if export_problems:
            report_path = write_failure_report(
                failed_process_dir=group_logs_dir,
                group_key=group_key,
                verification_type=(
                    "Export verification failed"
                ),
                problems=export_problems,
            )

            print(
                f"Failure report written: "
                f"{report_path.name}"
            )

            failed_bases = {
                problem["base"]
                for problem in export_problems
                if problem.get(
                    "base"
                )
            }

            moved_files = []

            for failed_base in failed_bases:
                moved_files.extend(
                    move_output_files_for_base(
                        output_dir=recipe_output_dir,
                        target_dir=input_dir,
                        base_name=failed_base,
                    )
                )

            print(
                f"Moved failed exported files "
                f"flat to machine root "
                f"for {group_key}: "
                f"{len(moved_files)}"
            )

        measurement_problems = (
            verify_measurements(
                recipe_output_dir,
                group_key,
            )
        )

        print_measurement_verification_result(
            measurement_problems,
            group_key,
        )

        if measurement_problems:
            report_path = write_failure_report(
                failed_process_dir=group_logs_dir,
                group_key=group_key,
                verification_type=(
                    "Measurement verification "
                    "failed"
                ),
                problems=measurement_problems,
            )

            print(
                f"Failure report written: "
                f"{report_path.name}"
            )

            failed_bases = {
                problem["base"]
                for problem
                in measurement_problems
                if problem.get(
                    "base"
                )
            }

            moved_files = []

            for failed_base in failed_bases:
                moved_files.extend(
                    move_output_files_for_base(
                        output_dir=recipe_output_dir,
                        target_dir=input_dir,
                        base_name=failed_base,
                    )
                )

            print(
                f"Moved failed measurement "
                f"files flat to machine root "
                f"for {group_key}: "
                f"{len(moved_files)}"
            )

        if (
            not export_problems
            and not measurement_problems
        ):
            target_powerbi_details_dir = (
                get_powerbi_details_dir_for_recipe(
                    recipe_name
                )
            )

            moved_powerbi_files = (
                move_powerbi_csv_files_to_details(
                    recipe_output_dir=(
                        recipe_output_dir
                    ),
                    powerbi_details_dir=(
                        target_powerbi_details_dir
                    ),
                    group_key=group_key,
                )
            )

            print(
                f"Moved Power BI CSV files "
                f"to {target_powerbi_details_dir} "
                f"for {group_key}: "
                f"{len(moved_powerbi_files)}"
            )   
        deleted_files = (
            cleanup_processed_group(
                unique_paths(
                    processed_input_files
                )
            )
        )

        print(
            f"Deleted processed input files "
            f"for {group_key}: "
            f"{len(deleted_files)}"
        )

    deleted_date_folders = (
        cleanup_empty_date_folders(
            input_dir
        )
    )

    if deleted_date_folders:
        print(
            f"Final cleanup deleted "
            f"date folders: "
            f"{len(deleted_date_folders)}"
        )

    moved_statistics_files = (
        move_statistics_folders_to_input_root(
            input_dir
        )
    )

    print(
        f"Moved Statistics files to "
        f"machine root Statistics folder: "
        f"{len(moved_statistics_files)}"
    )

    deleted_recipe_folders = (
        cleanup_empty_recipe_output_folders(
            input_dir
        )
    )

    if deleted_recipe_folders:
        print(
            f"Final cleanup deleted "
            f"recipe folders: "
            f"{len(deleted_recipe_folders)}"
        )


def main() -> None:
    """
    Writes the complete wrapper console output into:
    V:/Logs/<YYYYMMDD>/Successful/
    """

    run_timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    log_date_folder = datetime.now().strftime(
        "%Y%m%d"
    )

    success_log_dir = (
        LOGS_DIR
        / log_date_folder
        / "Successful"
    )

    success_log_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    success_log_file = (
        success_log_dir
        / f"{run_timestamp}_Success_Report.txt"
    )

    original_stdout = sys.stdout
    original_stderr = sys.stderr

    with success_log_file.open(
        "w",
        encoding="utf-8",
    ) as log_file:
        tee_stdout = TeeLogger(
            original_stdout,
            log_file,
        )

        tee_stderr = TeeLogger(
            original_stderr,
            log_file,
        )

        sys.stdout = tee_stdout
        sys.stderr = tee_stderr

        try:
            print(
                f"Success log started: "
                f"{success_log_file}"
            )

            print(
                "=" * 80
            )

            run_pipeline()

            print(
                "=" * 80
            )

            print(
                f"Success log written: "
                f"{success_log_file}"
            )

        finally:
            sys.stdout = (
                original_stdout
            )

            sys.stderr = (
                original_stderr
            )


if __name__ == "__main__":
    main()