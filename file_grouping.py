from pathlib import Path                    # Ordner/Dateien sauber lesen
from collections import defaultdict         # Dateien gruppieren -> automatisch Listen erstellen
import re                                   # Regex erkennen (Dateimuster)

from config_loader import machine_config


FILE_STRUCTURE_CONFIG = machine_config["file_structure"]

RECIPE_FILE_EXTENSION = FILE_STRUCTURE_CONFIG["recipe_file_extension"]
RECIPE_OUTPUT_SUFFIX = FILE_STRUCTURE_CONFIG["recipe_output_suffix"]
STATISTICS_FOLDER_NAME = FILE_STRUCTURE_CONFIG["statistics_folder_name"]

GROUP_PATTERN = re.compile(FILE_STRUCTURE_CONFIG["group_file_pattern"])
DATE_FOLDER_PATTERN = re.compile(FILE_STRUCTURE_CONFIG["date_folder_pattern"])


def find_file_groups(input_dir: Path) -> dict[str, dict]:
    groups = {}

    for recipe_file in input_dir.glob(f"*{RECIPE_FILE_EXTENSION}"):
        recipe_name = f"{recipe_file.stem}{RECIPE_OUTPUT_SUFFIX}"
        recipe_output_folder = input_dir / recipe_name

        if not recipe_output_folder.is_dir():
            continue

        temp_groups = defaultdict(list)

        for date_folder in recipe_output_folder.iterdir():
            if not date_folder.is_dir():
                continue

            if date_folder.name == STATISTICS_FOLDER_NAME:
                continue

            if not DATE_FOLDER_PATTERN.match(date_folder.name):
                continue

            for file_path in date_folder.iterdir():
                if not file_path.is_file():
                    continue

                match = GROUP_PATTERN.match(file_path.name)
                if not match:
                    continue

                group_key = f"{match.group('date')}_{match.group('time')}"
                temp_groups[group_key].append(file_path)

        for group_key, files in temp_groups.items():
            internal_group_id = f"{recipe_name}__{group_key}"

            groups[internal_group_id] = {
                "recipe_name": recipe_name,
                "group_key": group_key,
                "files": files,
            }

    return groups


# Helper function for printing the groups
def print_groups(groups: dict[str, dict]) -> None:
    for internal_group_id, group_info in groups.items():
        print(f"\nGroup: {internal_group_id}")
        print(f"  Recipe: {group_info['recipe_name']}")
        print(f"  Group key: {group_info['group_key']}")

        for file in group_info["files"]:
            print(f"  - {file.name}")


if __name__ == "__main__":
    input_dir = Path("input")
    groups = find_file_groups(input_dir)
    print_groups(groups)