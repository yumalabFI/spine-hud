import json
import os
import tempfile
from pathlib import Path

try:
    from .engine import (
        SpineValidationError,
        validate_spine_data,
    )
except ImportError:
    from engine import (
        SpineValidationError,
        validate_spine_data,
    )


class SpineStorageError(RuntimeError):
    pass


def load_spine(path: Path) -> dict:
    path = Path(path)

    if not path.exists():
        raise SpineStorageError(
            f"Spine file not found: {path}"
        )

    try:
        data = json.loads(
            path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as exc:
        raise SpineStorageError(
            f"Invalid JSON: {exc}"
        ) from exc
    except OSError as exc:
        raise SpineStorageError(
            f"Cannot read Spine file: {exc}"
        ) from exc

    try:
        validate_spine_data(data)
    except SpineValidationError as exc:
        raise SpineStorageError(
            f"Invalid Spine data: {exc}"
        ) from exc

    return data


def save_spine(path: Path, data: dict) -> None:
    path = Path(path)

    try:
        validate_spine_data(data)
    except SpineValidationError as exc:
        raise SpineStorageError(
            f"Refusing to save invalid Spine data: {exc}"
        ) from exc

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    content = (
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        )
        + "\n"
    )

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp:
            temp.write(content)
            temp.flush()
            os.fsync(temp.fileno())
            temp_path = Path(temp.name)

        os.replace(
            temp_path,
            path
        )

    except OSError as exc:
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass

        raise SpineStorageError(
            f"Cannot save Spine file: {exc}"
        ) from exc
