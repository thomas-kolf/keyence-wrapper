from pathlib import Path
import shutil
import os
import stat
import time
import re


MAX_LEFTOVER_FOLDER_SIZE_MB = 5

DATE_FOLDER_PATTERN = re.compile(r"^\d{8}$")

REAL_KEYENCE_SUFFIXES = {
    ".xlsx",
    ".csv",
    ".zmr",
    ".png",
}


def _make_writable(path: Path) -> None:
    os.chmod(path, stat.S_IWRITE)


def _get_folder_size_bytes(folder: Path) -> int:
    total_size = 0

    for file_path in folder.rglob("*"):
        if file_path.is_file():
            try:
                total_size += file_path.stat().st_size
            except OSError:
                pass

    return total_size


def _has_real_keyence_files(folder: Path) -> bool:
    for file_path in folder.rglob("*"):
        if not file_path.is_file():
            continue

        if file_path.suffix.lower() in REAL_KEYENCE_SUFFIXES:
            return True

    return False


def _delete_temp_files(folder: Path) -> list[Path]:
    deleted_temp_files = []

    for temp_file in folder.rglob("~$*"):
        if not temp_file.is_file():
            continue

        try:
            _make_writable(temp_file)
            temp_file.unlink()
            deleted_temp_files.append(temp_file)
        except OSError as error:
            print(f"WARNING: Could not delete temp file: {temp_file} | {error}")

    return deleted_temp_files


def _delete_file(file_path: Path) -> bool:
    try:
        _make_writable(file_path)
        file_path.unlink()
        return True
    except FileNotFoundError:
        return True
    except OSError as error:
        print(f"WARNING: Could not delete input file: {file_path} | {error}")
        return False


def _remove_folder_with_retry(folder: Path) -> bool:
    last_error = None

    for _ in range(15):
        try:
            folder.rmdir()
            return True

        except PermissionError as error:
            last_error = error
            time.sleep(0.5)

        except OSError as error:
            last_error = error

            try:
                shutil.rmtree(
                    folder,
                    onerror=lambda func, path, exc_info: (
                        os.chmod(path, stat.S_IWRITE),
                        func(path),
                    ),
                )
                return True

            except PermissionError as error:
                last_error = error
                time.sleep(0.5)

            except OSError as error:
                last_error = error
                time.sleep(0.5)

    print(f"WARNING: Could not delete folder after retries: {folder} | {last_error}")
    return False


def _can_delete_leftover_date_folder(folder: Path) -> bool:
    if not folder.is_dir():
        return False

    if not DATE_FOLDER_PATTERN.match(folder.name):
        return False

    _delete_temp_files(folder)

    if _has_real_keyence_files(folder):
        return False

    folder_size_mb = _get_folder_size_bytes(folder) / (1024 * 1024)

    if folder_size_mb > MAX_LEFTOVER_FOLDER_SIZE_MB:
        print(
            f"WARNING: Date folder not deleted because leftover size is too large: "
            f"{folder} ({folder_size_mb:.2f} MB)"
        )
        return False

    return True


def cleanup_processed_group(files: list[Path]) -> list[Path]:
    """
    Deletes processed normal Keyence input files after successful verification.

    Important:
    - Deletes only files passed from the normal date folder.
    - Does not touch Statistics folders.
    - Does not touch .zit recipe files.
    - Tries to delete the date folder afterwards if safe.
    """

    deleted_files = []
    affected_folders = set()

    for file_path in files:
        file_path = Path(file_path)

        if "Statistics" in file_path.parts:
            continue

        if file_path.suffix.lower() == ".zit":
            continue

        affected_folders.add(file_path.parent)

        if _delete_file(file_path):
            deleted_files.append(file_path)

    for folder in affected_folders:
        if _can_delete_leftover_date_folder(folder):
            folder_size_mb = _get_folder_size_bytes(folder) / (1024 * 1024)

            if _remove_folder_with_retry(folder):
                print(
                    f"Deleted leftover input date folder: {folder} "
                    f"({folder_size_mb:.2f} MB)"
                )

    return deleted_files


def cleanup_empty_date_folders(input_dir: Path) -> list[Path]:
    """
    Final cleanup pass after the full pipeline run.

    Scans recipe output folders:
    input/RecipeName_zit/YYYYMMDD/

    Important:
    - Does not touch Statistics.
    - Does not touch .zit recipe files.
    - Deletes only date folders that contain no real Keyence files
      and are below MAX_LEFTOVER_FOLDER_SIZE_MB.
    """

    deleted_folders = []

    for recipe_folder in input_dir.iterdir():
        if not recipe_folder.is_dir():
            continue

        for date_folder in recipe_folder.iterdir():
            if date_folder.name == "Statistics":
                continue

            if not _can_delete_leftover_date_folder(date_folder):
                continue

            folder_size_mb = _get_folder_size_bytes(date_folder) / (1024 * 1024)

            if _remove_folder_with_retry(date_folder):
                deleted_folders.append(date_folder)
                print(
                    f"Final cleanup deleted input date folder: {date_folder} "
                    f"({folder_size_mb:.2f} MB)"
                )

    return deleted_folders