from pathlib import Path

from file_grouping import find_file_groups
from validator import validate_group
from extractor import build_cell_data


def main() -> None:
    input_dir = Path("input")

    groups = find_file_groups(input_dir)

    for group_key, files in groups.items():
        result = validate_group(files)

        if result.valid:
            print(f"\n{group_key}: VALID | DMC = {result.dmc}")

            cell_data_list = build_cell_data(files)

            for cell_data in cell_data_list:
                print(
                    f"{cell_data['cell_dmc']} | "
                    f"raw_pos={cell_data['raw_position']} | "
                    f"quality={cell_data['quality']} | "
                    f"measurements={len(cell_data['measurements'])}"
                )

        else:
            print(f"\n{group_key}: INVALID | {result.reason}")


if __name__ == "__main__":
    main()