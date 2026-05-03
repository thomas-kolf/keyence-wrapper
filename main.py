from pathlib import Path

from file_grouping import find_file_groups
from validator import validate_group
from extractor import extract_metadata


def main() -> None:
    input_dir = Path("input")

    groups = find_file_groups(input_dir)

    for group_key, files in groups.items():
        result = validate_group(files)

        if result.valid:
            print(f"\n{group_key}: VALID | DMC = {result.dmc}")

            metadata_list = extract_metadata(files)

            for metadata in metadata_list:
                print(metadata)

        else:
            print(f"\n{group_key}: INVALID | {result.reason}")


if __name__ == "__main__":
    main()