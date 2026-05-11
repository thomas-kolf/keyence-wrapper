import csv
import json
from pathlib import Path

from config_loader import machine_config


MEASUREMENT_VERIFICATION_CONFIG = machine_config["measurement_verification"]

CSV_ENCODINGS = MEASUREMENT_VERIFICATION_CONFIG["csv_encodings"]
DECIMAL_COMMA_TO_DOT = MEASUREMENT_VERIFICATION_CONFIG["decimal_comma_to_dot"]
EMPTY_NUMERIC_VALUES = set(
    MEASUREMENT_VERIFICATION_CONFIG["empty_numeric_values"]
)

HEADER_ALIASES_CONFIG = MEASUREMENT_VERIFICATION_CONFIG["header_aliases"]
FIELD_MAPPING_CONFIG = MEASUREMENT_VERIFICATION_CONFIG["field_mapping"]
NUMERIC_FIELDS = set(MEASUREMENT_VERIFICATION_CONFIG["numeric_fields"])


def build_csv_to_json_fields() -> dict[str, str]:
    csv_to_json_fields = {}

    for alias_key, json_field in FIELD_MAPPING_CONFIG.items():
        aliases = HEADER_ALIASES_CONFIG.get(alias_key, [])

        for alias in aliases:
            csv_to_json_fields[alias] = json_field

    return csv_to_json_fields


CSV_TO_JSON_FIELDS = build_csv_to_json_fields()


def normalize_text(value) -> str | None:
    if value is None:
        return None

    value = str(value).strip()

    if value == "":
        return None

    return value


def normalize_number(value) -> str | None:
    value = normalize_text(value)

    if value is None:
        return None

    if DECIMAL_COMMA_TO_DOT:
        value = value.replace(",", ".")

    if value in EMPTY_NUMERIC_VALUES:
        return None

    number = float(value)

    if number.is_integer():
        return str(int(number))

    return str(number)


def normalize_value(value, field_name: str) -> str | None:
    if field_name in NUMERIC_FIELDS:
        return normalize_number(value)

    return normalize_text(value)


def normalize_csv_headers(headers: list[str | None]) -> list[str]:
    normalized_headers = []
    empty_header_count = 0

    for header in headers:
        header = normalize_text(header)

        if header is None:
            empty_header_count += 1

            if empty_header_count == 1:
                normalized_headers.append("detail")
            else:
                normalized_headers.append(f"empty_{empty_header_count}")

        else:
            normalized_headers.append(header)

    return normalized_headers


def read_csv_measurements(csv_path: Path) -> list[dict]:
    last_error = None

    for encoding in CSV_ENCODINGS:
        try:
            with csv_path.open("r", encoding=encoding, newline="") as file:
                reader = csv.reader(file, delimiter=";")

                raw_headers = next(reader)
                headers = normalize_csv_headers(raw_headers)

                rows = []

                for raw_row in reader:
                    csv_row = dict(zip(headers, raw_row))
                    measurement = {}

                    for csv_field, json_field in CSV_TO_JSON_FIELDS.items():
                        measurement[json_field] = csv_row.get(csv_field)

                    rows.append(measurement)

                return rows

        except UnicodeDecodeError as error:
            last_error = error

    raise UnicodeDecodeError(
        "unknown",
        b"",
        0,
        1,
        f"Could not decode CSV file {csv_path.name}. Last error: {last_error}",
    )


def read_json_measurements(json_path: Path) -> list[dict]:
    with json_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    return data["measurements"]


def verify_measurements(output_dir: Path, group_key: str | None = None) -> list[dict]:
    """
    Verifies that measurement data written into JSON matches the raw CSV.

    If group_key is given, only JSON files starting with that group_key are checked.
    """

    problems = []

    if group_key is None:
        json_files = list(output_dir.glob("*.json"))
    else:
        json_files = list(output_dir.glob(f"{group_key}_*.json"))

    for json_path in json_files:
        base = json_path.stem
        csv_path = output_dir / f"{base}.csv"

        if not csv_path.exists():
            problems.append(
                {
                    "base": base,
                    "problem": "missing_csv",
                    "details": csv_path.name,
                }
            )
            continue

        json_measurements = read_json_measurements(json_path)
        csv_measurements = read_csv_measurements(csv_path)

        if len(json_measurements) != len(csv_measurements):
            problems.append(
                {
                    "base": base,
                    "problem": "measurement_count_mismatch",
                    "json_count": len(json_measurements),
                    "csv_count": len(csv_measurements),
                }
            )
            continue

        for index, (json_row, csv_row) in enumerate(
            zip(json_measurements, csv_measurements),
            start=1,
        ):
            for csv_field, json_field in CSV_TO_JSON_FIELDS.items():
                json_value = normalize_value(json_row.get(json_field), json_field)
                csv_value = normalize_value(csv_row.get(json_field), json_field)

                if json_value != csv_value:
                    problems.append(
                        {
                            "base": base,
                            "problem": "value_mismatch",
                            "row": index,
                            "field": json_field,
                            "json_value": json_value,
                            "csv_value": csv_value,
                        }
                    )

    return problems


def print_measurement_verification_result(
    problems: list[dict],
    group_key: str | None = None,
) -> None:
    if group_key is None:
        label = ""
    else:
        label = f" for {group_key}"

    if not problems:
        print(f"Measurement verification OK{label}")
        return

    print(f"Measurement verification FAILED{label}")

    for problem in problems:
        print(f"\nBase: {problem['base']}")
        print(f"Problem: {problem['problem']}")

        if problem["problem"] == "missing_csv":
            print(f"Missing CSV: {problem['details']}")

        elif problem["problem"] == "measurement_count_mismatch":
            print(f"JSON count: {problem['json_count']}")
            print(f"CSV count: {problem['csv_count']}")

        elif problem["problem"] == "value_mismatch":
            print(f"Row: {problem['row']}")
            print(f"Field: {problem['field']}")
            print(f"JSON value: {problem['json_value']}")
            print(f"CSV value: {problem['csv_value']}")