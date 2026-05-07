from pathlib import Path
import tomllib


CONFIG_FILE = Path("machine_config.toml")


def load_machine_config(config_path: Path = CONFIG_FILE) -> dict:
    """
    Loads the central machine configuration file.

    The config file is intentionally stored as .toml so it can be opened
    and edited with normal text editors like Notepad.
    """

    if not config_path.exists():
        raise FileNotFoundError(
            f"Machine config file not found: {config_path}"
        )

    with config_path.open("rb") as config_file:
        return tomllib.load(config_file)


machine_config = load_machine_config()