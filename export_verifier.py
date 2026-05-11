from pathlib import Path

from config_loader import machine_config


EXPORT_VERIFICATION_CONFIG = machine_config["export_verification"]
PREVIEW_CONFIG = machine_config["preview"]

EXPECTED_SUFFIXES = EXPORT_VERIFICATION_CONFIG["expected_output_suffixes"]
PREVIEW_ENABLED = PREVIEW_CONFIG["enabled"]
PREVIEW_SOURCE_SUFFIXES = PREVIEW_CONFIG["preview_source_suffixes"]


def build_preview_output_suffixes() -> list[str]:
    """
    Builds expected preview suffixes from configured source image suffixes.

    Example:
    _h.png -> _h_preview.png
    _t.png -> _t_preview.png
    """

    preview_suffixes = []

    for source_suffix in PREVIEW_SOURCE_SUFFIXES:
        source_path = Path(source_suffix)
        preview_suffix = f"{source_path.stem}_preview{source_path.suffix}"
        preview_suffixes.append(preview_suffix)

    return preview_suffixes


def get_active_expected_suffixes() -> list[str]:
    """
    Returns expected output suffixes.

    If preview generation is disabled, preview files are not expected.
    """

    if PREVIEW_ENABLED:
        return EXPECTED_SUFFIXES

    preview_suffixes = build_preview_output_suffixes()

    return [
        suffix for suffix in EXPECTED_SUFFIXES
        if suffix not in preview_suffixes
    ]


def verify_exports(output_dir: Path, group_key: str | None = None) -> list[dict]:
    """
    Verifies that every exported cell has all expected output files.

    If group_key is given, only JSON files starting with that group_key are checked.
    """

    problems = []
    active_expected_suffixes = get_active_expected_suffixes()

    if group_key is None:
        json_files = list(output_dir.glob("*.json"))
    else:
        json_files = list(output_dir.glob(f"{group_key}_*.json"))

    for json_path in json_files:
        base = json_path.stem
        missing_files = []

        for suffix in active_expected_suffixes:
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