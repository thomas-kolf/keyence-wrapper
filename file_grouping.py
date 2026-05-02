from pathlib import Path                    #Ordner/Dateien sauber lesen
from collections import defaultdict         #Dateien gruppieren->automatisch listen erstellen
import re                                   #Regex erkennen (Dateienmuster)


GROUP_PATTERN = re.compile(r"^(?P<date>\d{8})_(?P<time>\d{6})_.*")


def find_file_groups(input_dir: Path) -> dict[str, list[Path]]:
    groups = defaultdict(list)

    for file_path in input_dir.rglob("*"):
        if not file_path.is_file():
            continue

        match = GROUP_PATTERN.match(file_path.name)
        if not match:
            continue

        group_key = f"{match.group('date')}_{match.group('time')}"
        groups[group_key].append(file_path)

    return dict(groups)


#Helper function for printing the groups
def print_groups(groups: dict[str, list[Path]]) -> None:
    for group_key, files in groups.items():
        print(f"\nGroup: {group_key}")
        for file in files:
            print(f"  - {file.name}")

if __name__ == "__main__":
    input_dir = Path("input")
    groups = find_file_groups(input_dir)
    print_groups(groups)
