from pathlib import Path
import shutil

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
)
from powerbi_csv_creator import create_powerbi_csv_from_json
from excel_image_embedder import embed_h_image_in_excel
from preview_generator import generate_previews
from export_verifier import verify_exports, print_export_verification_result
from measurement_verifier import verify_measurements, print_measurement_verification_result
from failed_process_handler import (
    write_failure_report,
    copy_related_files_with_standardized_names,
)
from input_cleanup import cleanup_processed_group, cleanup_empty_date_folders
from invalid_group_handler import write_invalid_group_report


PREVIEW_ENABLED = machine_config["preview"]["enabled"]


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


def write_json_and_powerbi_csv_output(
    cell_data: dict,
    output_dir: Path,
    group_key: str,
) -> tuple[Path, Path]:
    normalize_missing_dmc_for_output(cell_data)

    file_base_name = build_export_base_name(cell_data, group_key)

    json_file = write_cell_json(
        cell_data=cell_data,
        output_dir=output_dir,
        file_base_name=file_base_name,
    )

    powerbi_csv_file = create_powerbi_csv_from_json(json_file)

    return json_file, powerbi_csv_file


def copy_incomplete_cell_to_input(
    cell_data: dict,
    files: list[Path],
    input_dir: Path,
    group_key: str,
) -> list[Path]:
    """
    Copies existing files of one incomplete cell flat to input/.
    Uses standardized naming where possible.
    """

    normalize_missing_dmc_for_output(cell_data)

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
    Moves all already exported files for one failed exported cell base
    from data_lake_ready/<recipe>/ to input/.
    """

    target_dir.mkdir(parents=True, exist_ok=True)

    moved_files = []

    for source_file in output_dir.glob(f"{base_name}*"):
        if not source_file.is_file():
            continue

        target_file = target_dir / source_file.name

        if target_file.exists():
            target_file.unlink()

        shutil.move(str(source_file), str(target_file))
        moved_files.append(target_file)

    return moved_files


def get_existing_files_for_unassigned_source_stem(
    files: list[Path],
    source_stem: str,
) -> list[Path]:
    """
    Handles the edge case where raw files exist for a cell,
    but no Excel file exists, so no cell_data can be built.
    These files cannot be standardized safely.
    """

    existing_files = []

    for file_path in files:
        if not file_path.is_file():
            continue

        detected_stem = get_source_stem_from_raw_file(file_path)

        if detected_stem == source_stem:
            existing_files.append(file_path)

    if files:
        date_folder = Path(files[0]).parent
        pseudo_source_file = date_folder / f"{source_stem}.xlsx"
        statistics_file = find_statistics_file(pseudo_source_file)

        if statistics_file is not None:
            existing_files.append(statistics_file)

    return unique_paths(existing_files)


def copy_unassigned_failed_files_to_input(
    files: list[Path],
    input_dir: Path,
    group_key: str,
    source_stem: str,
) -> list[Path]:
    """
    Copies failed files that cannot be assigned to a cell_data object.
    Example: Excel is missing, but CSV/images/ZMR exist.
    """

    copied_files = []
    input_dir.mkdir(parents=True, exist_ok=True)

    source_files = get_existing_files_for_unassigned_source_stem(
        files=files,
        source_stem=source_stem,
    )

    for source_file in source_files:
        target_file = input_dir / f"{group_key}_UNSTANDARDIZED_{source_file.name}"

        if target_file.exists():
            target_file.unlink()

        shutil.copy2(source_file, target_file)
        copied_files.append(target_file)

    return copied_files


def main() -> None:
    input_dir = Path("input")
    output_dir = Path("data_lake_ready")
    logs_dir = Path("Logs")

    input_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)

    groups = find_file_groups(input_dir)

    print(f"Found groups: {len(groups)}")

    if not groups:
        print("No input groups found. Nothing to process.")
        return

    for internal_group_id, group_info in groups.items():
        recipe_name = group_info["recipe_name"]
        group_key = group_info["group_key"]
        files = group_info["files"]

        recipe_output_dir = output_dir / recipe_name
        recipe_output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{recipe_name} | {group_key}: START")

        raw_problems = verify_raw_group_completeness(files)

        try:
            cell_data_list = build_cell_data(files)

        except Exception as error:
            print(
                f"{recipe_name} | {group_key}: FAILED | "
                f"Could not build cell data: {type(error).__name__}: {error}"
            )

            problems = raw_problems or [
                {
                    "base": group_key,
                    "missing_files": [
                        f"Could not build cell data: {type(error).__name__}: {error}"
                    ],
                }
            ]

            report_path = write_failure_report(
                failed_process_dir=logs_dir,
                group_key=group_key,
                verification_type="Cell data creation failed",
                problems=problems,
            )

            print(f"Failure report written: {report_path.name}")
            continue

        complete_cells = []
        incomplete_cells = []
        processed_input_files = []

        cell_source_stems = set()

        for cell_data in cell_data_list:
            normalize_missing_dmc_for_output(cell_data)

            source_file = Path(cell_data["source_file"])
            cell_source_stems.add(source_file.stem)

            missing_files = find_missing_raw_files(cell_data, files)

            if missing_files:
                incomplete_cells.append(
                    {
                        "cell_data": cell_data,
                        "missing_files": missing_files,
                    }
                )
            else:
                complete_cells.append(cell_data)

        unassigned_raw_problems = []

        for problem in raw_problems:
            source_stem = problem.get("base")

            if source_stem not in cell_source_stems:
                unassigned_raw_problems.append(problem)

        if complete_cells:
            print(
                f"{recipe_name} | {group_key}: "
                f"complete cells = {len(complete_cells)}"
            )

        if incomplete_cells or unassigned_raw_problems:
            failure_problems = []

            for incomplete_cell in incomplete_cells:
                cell_data = incomplete_cell["cell_data"]
                source_file = Path(cell_data["source_file"])

                failure_problems.append(
                    {
                        "base": source_file.stem,
                        "missing_files": incomplete_cell["missing_files"],
                    }
                )

            failure_problems.extend(unassigned_raw_problems)

            report_path = write_failure_report(
                failed_process_dir=logs_dir,
                group_key=group_key,
                verification_type="Cell-level raw input completeness failed",
                problems=failure_problems,
            )

            print(f"Failure report written: {report_path.name}")

        for incomplete_cell in incomplete_cells:
            cell_data = incomplete_cell["cell_data"]

            copied_files = copy_incomplete_cell_to_input(
                cell_data=cell_data,
                files=files,
                input_dir=input_dir,
                group_key=group_key,
            )

            related_input_files = find_related_files(cell_data, files)
            processed_input_files.extend(related_input_files)

            print(
                f"{cell_data['cell_dmc']} | INCOMPLETE | "
                f"copied flat to input | files={len(copied_files)}"
            )

        for problem in unassigned_raw_problems:
            source_stem = problem.get("base")

            copied_files = copy_unassigned_failed_files_to_input(
                files=files,
                input_dir=input_dir,
                group_key=group_key,
                source_stem=source_stem,
            )

            source_files = get_existing_files_for_unassigned_source_stem(
                files=files,
                source_stem=source_stem,
            )

            processed_input_files.extend(source_files)

            print(
                f"{source_stem} | INCOMPLETE_UNASSIGNED | "
                f"copied flat to input | files={len(copied_files)}"
            )

        if not complete_cells:
            deleted_files = cleanup_processed_group(unique_paths(processed_input_files))

            print(
                f"{recipe_name} | {group_key}: no complete cells exported | "
                f"deleted processed input files={len(deleted_files)}"
            )

            continue

        missing_dmc_cells = [
            cell_data
            for cell_data in complete_cells
            if not cell_data.get("leadframe_dmc")
        ]

        if missing_dmc_cells:
            report_path = write_invalid_group_report(
                no_dmc_dir=logs_dir,
                group_key=group_key,
                reason=(
                    "Missing DMC in one or more complete cells. "
                    "Cells were exported to data_lake_ready with MISSING_DMC-XX naming."
                ),
            )

            print(f"Invalid report written: {report_path.name}")

        for cell_data in complete_cells:
            file_base_name = build_export_base_name(cell_data, group_key)

            output_file, powerbi_csv_file = write_json_and_powerbi_csv_output(
                cell_data=cell_data,
                output_dir=recipe_output_dir,
                group_key=group_key,
            )

            exported_files = export_related_files(
                cell_data=cell_data,
                file_group=files,
                output_dir=recipe_output_dir,
                group_key=group_key,
            )

            embedded_excel = embed_h_image_in_excel(
                output_dir=recipe_output_dir,
                file_base_name=file_base_name,
            )

            related_input_files = find_related_files(cell_data, files)
            processed_input_files.extend(related_input_files)

            if embedded_excel is not None:
                image_status = "image=embedded"
            else:
                image_status = "image=not_embedded"

            print(
                f"{cell_data['cell_dmc']} | "
                f"quality={cell_data['quality']} | "
                f"measurements={len(cell_data['measurements'])} | "
                f"JSON={output_file.name} | "
                f"PowerBI_CSV={powerbi_csv_file.name} | "
                f"files={len(exported_files)} | "
                f"{image_status}"
            )

        if PREVIEW_ENABLED:
            created_previews = generate_previews(recipe_output_dir)

            group_previews = [
                preview for preview in created_previews
                if preview.name.startswith(group_key)
            ]

            if group_previews:
                print(f"Previews created for {group_key}: {len(group_previews)}")
            else:
                print(f"No new previews needed for {group_key}")

        else:
            print(f"Preview generation disabled for {group_key}")

        export_problems = verify_exports(recipe_output_dir, group_key)
        print_export_verification_result(export_problems, group_key)

        if export_problems:
            report_path = write_failure_report(
                failed_process_dir=logs_dir,
                group_key=group_key,
                verification_type="Export verification failed",
                problems=export_problems,
            )

            print(f"Failure report written: {report_path.name}")

            failed_bases = {
                problem["base"]
                for problem in export_problems
                if problem.get("base")
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
                f"Moved failed exported files flat to input "
                f"for {group_key}: {len(moved_files)}"
            )

        measurement_problems = verify_measurements(recipe_output_dir, group_key)
        print_measurement_verification_result(measurement_problems, group_key)

        if measurement_problems:
            report_path = write_failure_report(
                failed_process_dir=logs_dir,
                group_key=group_key,
                verification_type="Measurement verification failed",
                problems=measurement_problems,
            )

            print(f"Failure report written: {report_path.name}")

            failed_bases = {
                problem["base"]
                for problem in measurement_problems
                if problem.get("base")
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
                f"Moved failed measurement files flat to input "
                f"for {group_key}: {len(moved_files)}"
            )

        deleted_files = cleanup_processed_group(unique_paths(processed_input_files))

        print(
            f"Deleted processed input files for {group_key}: "
            f"{len(deleted_files)}"
        )

    deleted_date_folders = cleanup_empty_date_folders(input_dir)

    if deleted_date_folders:
        print(f"Final cleanup deleted date folders: {len(deleted_date_folders)}")


if __name__ == "__main__":
    main()