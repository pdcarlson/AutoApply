"""Writes JSON files so that a reader never sees half of one."""
import json
import os
import time
from pathlib import Path
from typing import Any

# Windows can hold the target open for a moment (antivirus, the search indexer)
_REPLACE_ATTEMPTS = 5
_REPLACE_RETRY_SECONDS = 0.05


def dump_json(value: Any) -> str:
    """Return the value as the indented UTF-8 JSON the data files use."""
    return json.dumps(value, ensure_ascii=False, indent=2)


def atomic_write_text(path: Path, text: str) -> None:
    """Write `path` through `path.tmp` and os.replace, so readers never see half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        for attempt in range(_REPLACE_ATTEMPTS):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == _REPLACE_ATTEMPTS - 1:
                    raise
                time.sleep(_REPLACE_RETRY_SECONDS)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)
