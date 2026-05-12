from pathlib import Path
import csv
import json


POWERBI_SUFFIX = "_PowerBI.csv"

POWERBI_COLUMNS = [
    "Leadframe_DMC",
    "Pos",
    "Timestamp",
    "Elem 1",
    "Detail",
    "Elem 2",
    "Comment",
    "Classification",
    "Value",
    "Unit",
    "Target",
    "Upper Tolerance",
    "Lower Tolerance",
    "Name",
    "Product Name",
    "Device",
    "Path",
    "Processing",
    "Overall Result",
]


def create_powerbi_csv_from_json(json_file: Path) -> Path:
    with json_file.open("r", encoding="utf-8") as file:
        cell_data = json.load(file)

    output_file = json_file.with_name(f"{json_file.stem}{POWERBI_SUFFIX}")
    measurements = cell_data.get("measurements", [])

    with output_file.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=POWERBI_COLUMNS,
            delimiter=";",
        )
        writer.writeheader()

        for measurement in measurements:
            writer.writerow(
                {
                    "Leadframe_DMC": cell_data.get("leadframe_dmc"),
                    "Pos": cell_data.get("position"),
                    "Timestamp": cell_data.get("timestamp"),
                    "Elem 1": measurement.get("elem_1"),
                    "Detail": measurement.get("detail"),
                    "Elem 2": measurement.get("elem_2"),
                    "Comment": measurement.get("kommentar"),
                    "Classification": measurement.get("classification"),
                    "Value": measurement.get("value"),
                    "Unit": measurement.get("unit"),
                    "Target": measurement.get("target"),
                    "Upper Tolerance": measurement.get("upper_tolerance"),
                    "Lower Tolerance": measurement.get("lower_tolerance"),
                    "Name": cell_data.get("name"),
                    "Product Name": cell_data.get("product_name"),
                    "Device": cell_data.get("device"),
                    "Path": cell_data.get("path"),
                    "Processing": cell_data.get("processing"),
                    "Overall Result": cell_data.get("overall_result"),
                }
            )

    return output_file