from pathlib import Path


EXPECTED_SUFFIXES = [
    ".json",
    ".xlsx",
    ".csv",
    ".zmr",
    "_h.png",
    "_t.png",
    "_h_preview.png",
    "_t_preview.png",
]


def verify_exports(output_dir: Path) -> list[dict]:
    """
    Verifies that every exported cell has all expected output files.

    Basis:
    - every .json file in output_dir
    - base filename = json_path.stem

    Returns:
    - list of problems
    - empty list means everything is complete
    """

    problems = []

    json_files = list(output_dir.glob("*.json"))

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


def print_export_verification_result(problems: list[dict]) -> None:
    """
    Prints a readable verification result.
    """

    if not problems:
        print("Export verification OK")
        return

    print("Export verification FAILED")

    for problem in problems:
        print(f"\nBase: {problem['base']}")
        print("Missing files:")

        for missing_file in problem["missing_files"]:
            print(f"  - {missing_file}")