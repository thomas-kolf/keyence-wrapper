from pathlib import Path

from config_loader import machine_config


EXPECTED_SUFFIXES = machine_config["export_verification"]["expected_output_suffixes"]


def verify_exports(output_dir: Path, group_key: str | None = None) -> list[dict]:
    """
    Verifies that every exported cell has all expected output files.

    If group_key is given, only JSON files starting with that group_key are checked.
    """

    problems = []

    if group_key is None:
        json_files = list(output_dir.glob("*.json"))
    else:
        json_files = list(output_dir.glob(f"{group_key}_*.json"))

    for json_path in json_files:
        base = json_path.stem
        missing_files = []

        for suffix in EXPECTED_SUFFIXES:
            expected_file = output_dir / f"{base}{suffix}"

            if not expected_file.exists():
                missing_files.append(expected_file.name)

        if missing_files:
            problems.append(
                {
                    "base": base,
                    "missing_files": missing_files,
                }
            )

    return problems


def print_export_verification_result(
    problems: list[dict],
    group_key: str | None = None,
) -> None:
    if group_key is None:
        label = ""
    else:
        label = f" for {group_key}"

    if not problems:
        print(f"Export verification OK{label}")
        return

    print(f"Export verification FAILED{label}")

    for problem in problems:
        print(f"\nBase: {problem['base']}")
        print("Missing files:")

        for missing_file in problem["missing_files"]:
            print(f"  - {missing_file}")