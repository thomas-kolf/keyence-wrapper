from pathlib import Path
import json


def read_cell_json(json_file: Path) -> dict:
    with json_file.open("r", encoding="utf-8") as file:
        return json.load(file)


def read_all_cell_jsons(input_dir: Path) -> list[dict]:
    cell_data_list = []

    for json_file in input_dir.glob("*.json"):
        cell_data = read_cell_json(json_file)
        cell_data_list.append(cell_data)

    return cell_data_list


def print_cell_summary(cell_data_list: list[dict]) -> None:
    print(f"Loaded cells: {len(cell_data_list)}")

    for cell in cell_data_list:
        print(
            f"{cell['cell_dmc']} | "
            f"quality={cell['quality']} | "
            f"measurements={len(cell['measurements'])}"
        )


if __name__ == "__main__":
    input_dir = Path("data_lake_ready")
    cells = read_all_cell_jsons(input_dir)
    print_cell_summary(cells)