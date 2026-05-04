from pathlib import Path

from file_grouping import find_file_groups
from validator import validate_group
from extractor import build_cell_data, write_cell_json
from file_exporter import export_related_files, build_export_base_name
from preview_generator import generate_previews
from export_verifier import verify_exports, print_export_verification_result
from measurement_verifier import verify_measurements, print_measurement_verification_result
from failed_process_handler import move_failed_group, write_failure_report


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

    for group_key, files in groups.items():
        result = validate_group(files)

        if result.valid:
            cell_data_list = build_cell_data(files)

            print(
                f"\n{group_key}: VALID | "
                f"DMC = {result.dmc} | "
                f"cells = {len(cell_data_list)}"
            )

            for cell_data in cell_data_list:
                file_base_name = build_export_base_name(cell_data, group_key)

                output_file = write_cell_json(
                    cell_data=cell_data,
                    output_dir=output_dir,
                    file_base_name=file_base_name,
                )

                exported_files = export_related_files(
                    cell_data=cell_data,
                    file_group=files,
                    output_dir=output_dir,
                    group_key=group_key,
                )

                print(
                    f"{cell_data['cell_dmc']} | "
                    f"quality={cell_data['quality']} | "
                    f"measurements={len(cell_data['measurements'])} | "
                    f"JSON={output_file.name} | "
                    f"files={len(exported_files)}"
                )

            created_previews = generate_previews(output_dir)

            group_previews = [
                preview for preview in created_previews
                if preview.name.startswith(group_key)
            ]

            if group_previews:
                print(f"Previews created for {group_key}: {len(group_previews)}")
            else:
                print(f"No new previews needed for {group_key}")

            export_problems = verify_exports(output_dir, group_key)
            print_export_verification_result(export_problems, group_key)

            if export_problems:
                report_path = write_failure_report(
                    failed_process_dir=failed_dir,
                    group_key=group_key,
                    verification_type="Export verification failed",
                    problems=export_problems,
                )

                print(f"Failure report written: {report_path.name}")

                moved_files = move_failed_group(
                    output_dir=output_dir,
                    failed_process_dir=failed_dir,
                    group_key=group_key,
                )

                print(
                    f"Moved failed export files to failed_process "
                    f"for {group_key}: {len(moved_files)}"
                )

            measurement_problems = verify_measurements(output_dir, group_key)
            print_measurement_verification_result(measurement_problems, group_key)

            if measurement_problems:
                report_path = write_failure_report(
                    failed_process_dir=failed_dir,
                    group_key=group_key,
                    verification_type="Measurement verification failed",
                    problems=measurement_problems,
                )

                print(f"Failure report written: {report_path.name}")

                moved_files = move_failed_group(
                    output_dir=output_dir,
                    failed_process_dir=failed_dir,
                    group_key=group_key,
                )

                print(
                    f"Moved failed measurement files to failed_process "
                    f"for {group_key}: {len(moved_files)}"
                )

        else:
            print(f"\n{group_key}: INVALID | {result.reason}")


if __name__ == "__main__":
    main()