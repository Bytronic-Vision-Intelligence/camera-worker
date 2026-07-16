from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_CONFIG_PATH_OVERRIDE: Path | None = None


def _config_path() -> Path:
    if _CONFIG_PATH_OVERRIDE is not None:
        return _CONFIG_PATH_OVERRIDE
    return Path(__file__).resolve().parent / "config.yaml"


def set_config_path(path: str | Path | None) -> None:
    """Override the config file path for this process."""
    global _CONFIG_PATH_OVERRIDE
    if path is None:
        _CONFIG_PATH_OVERRIDE = None
        return
    _CONFIG_PATH_OVERRIDE = Path(path).resolve()


def get_config() -> dict:
    """Read and return configuration from the local `config.yaml` next to this module.

    Returns an empty dict if the file is missing or empty.
    """
    path = _config_path()
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    return config


def get_section(section: str) -> dict:
    """Return a top-level config subsection as a dict (empty dict if missing)."""
    if not section:
        raise ValueError("Section cannot be empty.")
    value = get_config().get(section)
    return value if isinstance(value, dict) else {}


def return_config_value(key: str) -> Any:
    """Return the value for a dot-separated key path in the loaded config.

    Examples: ``camera.camera_type``, ``archiving.archive_directory``.

    Raises ValueError for empty keys and KeyError when the path is missing.
    """
    if not key:
        raise ValueError("Key cannot be empty.")

    config = get_config()
    current: Any = config
    for part in key.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(f"Key '{key}' not found in configuration.")
        current = current[part]
    return current
