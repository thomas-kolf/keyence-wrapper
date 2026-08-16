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

    # Precalculated Power BI helper columns
    "Cell Key",
    "Is NOK",
    "Is OK",
    "Cell Is NOK",
    "Upper Limit",
    "Lower Limit",
    "Target Line",
    "Classification Color",
]


def _to_float_or_none(value):
    if value in (None, ""):
        return None

    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _calculate_limit(target, tolerance):
    target_value = _to_float_or_none(target)
    tolerance_value = _to_float_or_none(tolerance)

    if target_value is None or tolerance_value is None:
        return None

    return target_value + tolerance_value


def _build_cell_key(leadframe_dmc, position):
    dmc = leadframe_dmc if leadframe_dmc not in (None, "") else "MISSING_DMC"
    return f"{dmc}-{position}"


def create_powerbi_csv_from_json(json_file: Path) -> Path:
    with json_file.open("r", encoding="utf-8") as file:
        cell_data = json.load(file)

    output_file = json_file.with_name(f"{json_file.stem}{POWERBI_SUFFIX}")
    measurements = cell_data.get("measurements", [])

    leadframe_dmc = cell_data.get("leadframe_dmc")
    position = cell_data.get("position")
    cell_key = _build_cell_key(leadframe_dmc, position)

    cell_is_nok = int(
        any(
            measurement.get("classification") == "n.i.O."
            for measurement in measurements
        )
    )

    with output_file.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=POWERBI_COLUMNS,
            delimiter=",",
        )
        writer.writeheader()

        for measurement in measurements:
            classification = measurement.get("classification")

            is_nok = int(classification == "n.i.O.")
            is_ok = int(classification == "OK")

            target = measurement.get("target")
            upper_tolerance = measurement.get("upper_tolerance")
            lower_tolerance = measurement.get("lower_tolerance")

            writer.writerow(
                {
                    "Leadframe_DMC": leadframe_dmc,
                    "Pos": position,
                    "Timestamp": cell_data.get("timestamp"),
                    "Elem 1": measurement.get("elem_1"),
                    "Detail": measurement.get("detail"),
                    "Elem 2": measurement.get("elem_2"),
                    "Comment": measurement.get("kommentar"),
                    "Classification": classification,
                    "Value": measurement.get("value"),
                    "Unit": measurement.get("unit"),
                    "Target": target,
                    "Upper Tolerance": upper_tolerance,
                    "Lower Tolerance": lower_tolerance,
                    "Name": cell_data.get("name"),
                    "Product Name": cell_data.get("product_name"),
                    "Device": cell_data.get("device"),
                    "Path": cell_data.get("path"),
                    "Processing": cell_data.get("processing"),
                    "Overall Result": cell_data.get("overall_result"),

                    # Precalculated Power BI helper columns
                    "Cell Key": cell_key,
                    "Is NOK": is_nok,
                    "Is OK": is_ok,
                    "Cell Is NOK": cell_is_nok,
                    "Upper Limit": _calculate_limit(target, upper_tolerance),
                    "Lower Limit": _calculate_limit(target, lower_tolerance),
                    "Target Line": _to_float_or_none(target),
                    "Classification Color": "#F4CCCC" if is_nok else "#FFFFFF",
                }
            )

    return output_file