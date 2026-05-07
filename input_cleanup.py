from pathlib import Path
import shutil
import os
import stat
import time


MAX_LEFTOVER_FOLDER_SIZE_MB = 5

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
    for _ in range(10):
        try:
            shutil.rmtree(
                folder,
                onerror=lambda func, path, exc_info: (
                    os.chmod(path, stat.S_IWRITE),
                    func(path),
                ),
            )
            return True
        except PermissionError:
            time.sleep(0.3)
        except OSError as error:
            print(f"WARNING: Could not delete folder: {folder} | {error}")
            return False

    return False


def cleanup_processed_group(files: list[Path]) -> list[Path]:
    """
    Deletes processed normal Keyence input files after successful verification.

    Important:
    - Deletes only files passed from the normal date folder.
    - Does not touch Statistics folders.
    - Does not touch .zit recipe files.
    - Deletes leftover date folder only if no real Keyence files remain
      and leftover size is below MAX_LEFTOVER_FOLDER_SIZE_MB.
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
        _delete_temp_files(folder)

        if _has_real_keyence_files(folder):
            continue

        folder_size_mb = _get_folder_size_bytes(folder) / (1024 * 1024)

        if folder_size_mb <= MAX_LEFTOVER_FOLDER_SIZE_MB:
            deleted = _remove_folder_with_retry(folder)

            if deleted:
                print(
                    f"Deleted leftover input date folder: {folder} "
                    f"({folder_size_mb:.2f} MB)"
                )
        else:
            print(
                f"WARNING: Date folder not deleted because leftover size is too large: "
                f"{folder} ({folder_size_mb:.2f} MB)"
            )

    return deleted_files