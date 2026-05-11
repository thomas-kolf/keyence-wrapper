from pathlib import Path

from config_loader import machine_config

from file_grouping import find_file_groups
from validator import validate_group
from extractor import build_cell_data, write_cell_json
from file_exporter import export_related_files, build_export_base_name
from excel_image_embedder import embed_h_image_in_excel
from preview_generator import generate_previews
from export_verifier import verify_exports, print_export_verification_result
from measurement_verifier import verify_measurements, print_measurement_verification_result
from failed_process_handler import move_failed_group, write_failure_report
from input_cleanup import cleanup_processed_group, cleanup_empty_date_folders
from invalid_group_handler import (
    copy_invalid_group,
    verify_invalid_group_copy,
    write_invalid_group_report,
)


PREVIEW_ENABLED = machine_config["preview"]["enabled"]


def main() -> None:
    input_dir = Path("input")
    output_dir = Path("data_lake_ready")
    no_dmc_dir = Path("no_dmc_related")
    failed_dir = Path("failed_process")

    input_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)
    no_dmc_dir.mkdir(exist_ok=True)
    failed_dir.mkdir(exist_ok=True)

    groups = find_file_groups(input_dir)

    for internal_group_id, group_info in groups.items():
        recipe_name = group_info["recipe_name"]
        group_key = group_info["group_key"]
        files = group_info["files"]

        recipe_output_dir = output_dir / recipe_name
        recipe_no_dmc_dir = no_dmc_dir / recipe_name
        recipe_failed_dir = failed_dir / recipe_name

        recipe_output_dir.mkdir(exist_ok=True)
        recipe_no_dmc_dir.mkdir(exist_ok=True)
        recipe_failed_dir.mkdir(exist_ok=True)

        result = validate_group(files)

        if result.valid:
            cell_data_list = build_cell_data(files)

            print(
                f"\n{recipe_name} | {group_key}: VALID | "
                f"DMC = {result.dmc} | "
                f"cells = {len(cell_data_list)}"
            )

            for cell_data in cell_data_list:
                file_base_name = build_export_base_name(cell_data, group_key)

                output_file = write_cell_json(
                    cell_data=cell_data,
                    output_dir=recipe_output_dir,
                    file_base_name=file_base_name,
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

                if embedded_excel is not None:
                    image_status = "image=embedded"
                else:
                    image_status = "image=not_embedded"

                print(
                    f"{cell_data['cell_dmc']} | "
                    f"quality={cell_data['quality']} | "
                    f"measurements={len(cell_data['measurements'])} | "
                    f"JSON={output_file.name} | "
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
                    failed_process_dir=recipe_failed_dir,
                    group_key=group_key,
                    verification_type="Export verification failed",
                    problems=export_problems,
                )

                print(f"Failure report written: {report_path.name}")

                moved_files = move_failed_group(
                    output_dir=recipe_output_dir,
                    failed_process_dir=recipe_failed_dir,
                    group_key=group_key,
                )

                print(
                    f"Moved failed export files to failed_process "
                    f"for {group_key}: {len(moved_files)}"
                )

            measurement_problems = verify_measurements(recipe_output_dir, group_key)
            print_measurement_verification_result(measurement_problems, group_key)

            if measurement_problems:
                report_path = write_failure_report(
                    failed_process_dir=recipe_failed_dir,
                    group_key=group_key,
                    verification_type="Measurement verification failed",
                    problems=measurement_problems,
                )

                print(f"Failure report written: {report_path.name}")

                moved_files = move_failed_group(
                    output_dir=recipe_output_dir,
                    failed_process_dir=recipe_failed_dir,
                    group_key=group_key,
                )

                print(
                    f"Moved failed measurement files to failed_process "
                    f"for {group_key}: {len(moved_files)}"
                )

            if not export_problems and not measurement_problems:
                deleted_files = cleanup_processed_group(files)

                print(
                    f"Deleted processed input files for {group_key}: "
                    f"{len(deleted_files)}"
                )

        else:
            print(f"\n{recipe_name} | {group_key}: INVALID | {result.reason}")

            copied_files = copy_invalid_group(
                files=files,
                no_dmc_dir=recipe_no_dmc_dir,
            )

            copy_problems = verify_invalid_group_copy(
                files=files,
                no_dmc_dir=recipe_no_dmc_dir,
            )

            if copy_problems:
                write_invalid_group_report(
                    no_dmc_dir=recipe_no_dmc_dir,
                    group_key=group_key,
                    reason=result.reason,
                    problems=copy_problems,
                )

                print(f"Invalid group copy FAILED for {group_key}")

            else:
                write_invalid_group_report(
                    no_dmc_dir=recipe_no_dmc_dir,
                    group_key=group_key,
                    reason=result.reason,
                )

                print(
                    f"Invalid group copied to no_dmc_related for {group_key}: "
                    f"{len(copied_files)} files"
                )

    deleted_date_folders = cleanup_empty_date_folders(input_dir)

    if deleted_date_folders:
        print(f"Final cleanup deleted date folders: {len(deleted_date_folders)}")


if __name__ == "__main__":
    main()