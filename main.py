from pathlib import Path

from file_grouping import find_file_groups
from validator import validate_group
from extractor import build_cell_data, write_cell_json
from file_exporter import export_related_files, build_export_base_name


def main() -> None:
    input_dir = Path("input")
    output_dir = Path("data_lake_ready")

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
                    file_base_name=file_base_name
                )

                exported_files = export_related_files(
                    cell_data=cell_data,
                    file_group=files,
                    output_dir=output_dir,
                    group_key=group_key
                )

                print(
                    f"{cell_data['cell_dmc']} | "
                    f"quality={cell_data['quality']} | "
                    f"measurements={len(cell_data['measurements'])} | "
                    f"JSON={output_file.name} | "
                    f"files={len(exported_files)}"
                )

        else:
            print(f"\n{group_key}: INVALID | {result.reason}")


if __name__ == "__main__":
    main()