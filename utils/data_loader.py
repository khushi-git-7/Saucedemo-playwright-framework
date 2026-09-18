"""Test-data loading helpers.

Two jobs:

1. Resolve data files relative to the repository root, so tests behave the same
   no matter which directory pytest was started from (important for `-n auto`,
   Docker and CI).
2. Expand `${PLACEHOLDER}` tokens against `utils.config.Config`, which keeps
   credentials in the environment instead of in a committed JSON file.
"""

import json
import re
from pathlib import Path

from utils.config import Config

_PLACEHOLDER = re.compile(r"\$\{([A-Z0-9_]+)\}")


def resolve(value):
    """Replace ``${NAME}`` tokens in a string with the matching Config value."""
    if not isinstance(value, str):
        return value

    def _replace(match: re.Match) -> str:
        name = match.group(1)
        if not hasattr(Config, name):
            raise KeyError(
                f"Test data references ${{{name}}} but utils.config.Config "
                f"has no such setting."
            )
        return str(getattr(Config, name))

    return _PLACEHOLDER.sub(_replace, value)


def _resolve_deep(node):
    if isinstance(node, dict):
        return {key: _resolve_deep(val) for key, val in node.items()}
    if isinstance(node, list):
        return [_resolve_deep(item) for item in node]
    return resolve(node)


def load_json(filename: str):
    """Load a JSON file from ``test_data/`` with placeholders resolved."""
    path = Path(filename)
    if not path.is_absolute():
        path = Config.TEST_DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Test data file not found: {path}")
    with path.open(encoding="utf-8") as handle:
        return _resolve_deep(json.load(handle))
