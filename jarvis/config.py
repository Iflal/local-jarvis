"""Configuration loading and path resolution."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    default_path = PROJECT_ROOT / "config.json"
    with default_path.open("r", encoding="utf-8") as handle:
        defaults = json.load(handle)

    selected = Path(path).expanduser().resolve() if path else default_path
    if selected == default_path:
        config = defaults
    else:
        with selected.open("r", encoding="utf-8") as handle:
            config = _deep_merge(defaults, json.load(handle))

    database = Path(config["database"]).expanduser()
    if not database.is_absolute():
        database = PROJECT_ROOT / database
    config["database"] = str(database.resolve())
    config["search_roots"] = [
        str(Path(item).expanduser().resolve()) for item in config.get("search_roots", [])
    ]
    return config

