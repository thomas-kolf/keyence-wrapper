from pathlib import Path
import shutil


def copy_invalid_group(
    files: list[Path],
    no_dmc_dir: Path,
) -> list[Path]:
    copied_files: list[Path] = []

    for source_file in files:
        target_file = no_dmc_dir / source_file.name

        target_file.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(source_file, target_file)
        copied_files.append(target_file)

    return copied_files


def verify_invalid_group_copy(
    files: list[Path],
    no_dmc_dir: Path,
) -> list[dict]:
    problems: list[dict] = []

    for source_file in files:
        target_file = no_dmc_dir / source_file.name

        if not target_file.exists():
            problems.append(
                {
                    "type": "missing_copied_file",
                    "source": str(source_file),
                    "expected_target": str(target_file),
                }
            )

    return problems


def write_invalid_group_report(
    no_dmc_dir: Path,
    group_key: str,
    reason: str,
    problems: list[dict] | None = None,
) -> Path:
    report_path = no_dmc_dir / f"{group_key}_INVALID_REPORT.txt"

    lines = [
        "INVALID GROUP REPORT",
        "",
        f"group_key: {group_key}",
        f"reason: {reason}",
        "",
    ]

    if problems:
        lines.append("copy problems:")
        for problem in problems:
            lines.append(f"- type: {problem.get('type')}")
            lines.append(f"  source: {problem.get('source')}")
            lines.append(f"  expected_target: {problem.get('expected_target')}")
    else:
        lines.append("copy verification: OK")

    report_path.write_text("\n".join(lines), encoding="utf-8")

    return report_path