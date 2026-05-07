from pathlib import Path                    # Ordner/Dateien sauber lesen
from collections import defaultdict         # Dateien gruppieren -> automatisch Listen erstellen
import re                                   # Regex erkennen (Dateimuster)


GROUP_PATTERN = re.compile(r"^(?P<date>\d{8})_(?P<time>\d{6})_.*")
DATE_FOLDER_PATTERN = re.compile(r"^\d{8}$")


def find_file_groups(input_dir: Path) -> dict[str, dict]:
    groups = {}

    for recipe_file in input_dir.glob("*.zit"):
        recipe_name = f"{recipe_file.stem}_zit"
        recipe_output_folder = input_dir / recipe_name

        if not recipe_output_folder.is_dir():
            continue

        temp_groups = defaultdict(list)

        for date_folder in recipe_output_folder.iterdir():
            if not date_folder.is_dir():
                continue

            if date_folder.name == "Statistics":
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