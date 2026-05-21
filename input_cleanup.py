from pathlib import Path
import shutil
import os
import stat
import time
import re
import subprocess

from config_loader import machine_config


INPUT_CLEANUP_CONFIG = machine_config["input_cleanup"]
FILE_STRUCTURE_CONFIG = machine_config["file_structure"]

DELETE_PROCESSED_FILES = INPUT_CLEANUP_CONFIG["delete_processed_files"]
KEEP_STATISTICS_FOLDER = INPUT_CLEANUP_CONFIG["keep_statistics_folder"]
KEEP_RECIPE_FILES = INPUT_CLEANUP_CONFIG["keep_recipe_files"]
MAX_LEFTOVER_FOLDER_SIZE_MB = INPUT_CLEANUP_CONFIG["max_leftover_folder_size_mb"]
DELETE_RETRY_COUNT = INPUT_CLEANUP_CONFIG["delete_retry_count"]
DELETE_RETRY_WAIT_SECONDS = INPUT_CLEANUP_CONFIG["delete_retry_wait_seconds"]

STATISTICS_FOLDER_NAME = FILE_STRUCTURE_CONFIG["statistics_folder_name"]
RECIPE_FILE_EXTENSION = FILE_STRUCTURE_CONFIG["recipe_file_extension"]
DATE_FOLDER_PATTERN = re.compile(FILE_STRUCTURE_CONFIG["date_folder_pattern"])


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
    folder = folder.resolve()

    for _ in range(DELETE_RETRY_COUNT):
        try:
            _make_writable(folder)
            folder.rmdir()
            return True

        except Exception as error:
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

        except Exception as error:
            last_error = error

        try:
            subprocess.run(
                ["attrib", "-R", "-S", "-H", str(folder), "/S", "/D"],
                shell=True,
                check=False,
            )

            subprocess.run(
                ["cmd", "/c", "rmdir", "/S", "/Q", str(folder)],
                shell=False,
                check=False,
            )

            if not folder.exists():
                return True

        except Exception as error:
            last_error = error

        time.sleep(DELETE_RETRY_WAIT_SECONDS)

    print(f"WARNING: Could not delete folder after retries: {folder} | {last_error}")
    return False


def _can_delete_leftover_date_folder(folder: Path) -> bool:
    if not folder.is_dir():
        return False

    if not DATE_FOLDER_PATTERN.match(folder.name):
        return False

    _delete_temp_files(folder)

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
    Deletes processed normal input files after successful verification.

    Important:
    - Deletes only files passed from the normal date folder.
    - Can be disabled in machine_config.toml.
    - Can protect Statistics folders.
    - Can protect recipe files.
    - Date folder deletion is handled only by cleanup_empty_date_folders().
    """

    deleted_files = []

    if not DELETE_PROCESSED_FILES:
        return deleted_files

    for file_path in files:
        file_path = Path(file_path)

        if KEEP_STATISTICS_FOLDER and STATISTICS_FOLDER_NAME in file_path.parts:
            continue

        if KEEP_RECIPE_FILES and file_path.suffix.lower() == RECIPE_FILE_EXTENSION:
            continue

        if _delete_file(file_path):
            deleted_files.append(file_path)

    return deleted_files


def cleanup_empty_date_folders(input_dir: Path) -> list[Path]:
    """
    Final cleanup pass after the full pipeline run.

    Scans recipe output folders:
    input/RecipeName_zit/YYYYMMDD/

    Important:
    - Can protect Statistics folders.
    - Deletes only date folders that are below max_leftover_folder_size_mb.
    """

    deleted_folders = []

    for recipe_folder in input_dir.iterdir():
        if not recipe_folder.is_dir():
            continue

        for date_folder in recipe_folder.iterdir():
            if KEEP_STATISTICS_FOLDER and date_folder.name == STATISTICS_FOLDER_NAME:
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

def move_statistics_folders_to_input_root(input_dir: Path) -> list[Path]:
    """
    Moves Statistics folders from recipe output folders to input/Statistics.

    Example:
    input/EMB_Gan_Prüfvorlage_zit/Statistics/YYYYMMDD/
    -> input/Statistics/YYYYMMDD/

    Existing input/Statistics content is merged.
    """

    moved_items = []

    target_statistics_root = input_dir / STATISTICS_FOLDER_NAME
    target_statistics_root.mkdir(parents=True, exist_ok=True)

    for recipe_folder in input_dir.iterdir():
        if not recipe_folder.is_dir():
            continue

        if recipe_folder.name == STATISTICS_FOLDER_NAME:
            continue

        source_statistics_root = recipe_folder / STATISTICS_FOLDER_NAME

        if not source_statistics_root.is_dir():
            continue

        for source_item in source_statistics_root.iterdir():
            target_item = target_statistics_root / source_item.name

            if source_item.is_dir():
                target_item.mkdir(parents=True, exist_ok=True)

                for source_file in source_item.rglob("*"):
                    if not source_file.is_file():
                        continue

                    relative_path = source_file.relative_to(source_item)
                    target_file = target_item / relative_path
                    target_file.parent.mkdir(parents=True, exist_ok=True)

                    if target_file.exists():
                        target_file.unlink()

                    shutil.move(str(source_file), str(target_file))
                    moved_items.append(target_file)

            else:
                if target_item.exists():
                    target_item.unlink()

                shutil.move(str(source_item), str(target_item))
                moved_items.append(target_item)

        _remove_folder_with_retry(source_statistics_root)

    return moved_items


def cleanup_empty_recipe_output_folders(input_dir: Path) -> list[Path]:
    """
    Deletes empty recipe output folders after normal files were cleaned
    and Statistics was moved to input/Statistics.
    """

    deleted_folders = []

    for recipe_folder in input_dir.iterdir():
        if not recipe_folder.is_dir():
            continue

        if recipe_folder.name == STATISTICS_FOLDER_NAME:
            continue

        if any(recipe_folder.iterdir()):
            continue

        if _remove_folder_with_retry(recipe_folder):
            deleted_folders.append(recipe_folder)
            print(f"Final cleanup deleted empty recipe folder: {recipe_folder}")

    return deleted_folders