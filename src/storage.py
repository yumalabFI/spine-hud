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



def roadmap_markdown(data: dict) -> str:
    project = data.get("project", "Project")

    lines = [
        f"# {project} Roadmap",
        "",
        "> Generated automatically from `spine.json`.",
        "",
    ]

    def write_nodes(nodes, depth=0):
        for node in nodes:
            name = node.get("name", "Unnamed")
            status = node.get("status", "planned")
            children = node.get("children", [])

            indent = "  " * depth

            if children:
                lines.append(
                    f"{indent}- **{name}**"
                )
            else:
                mark = "x" if status == "done" else " "

                suffix = ""

                if status == "active":
                    suffix = " — active"
                elif status == "blocked":
                    suffix = " — blocked"

                lines.append(
                    f"{indent}- [{mark}] {name}{suffix}"
                )

            write_nodes(
                children,
                depth + 1
            )

    write_nodes(
        data.get("tree", [])
    )

    return "\n".join(lines) + "\n"


def update_roadmap_document(
    spine_path: Path,
    data: dict
) -> None:
    spine_path = Path(spine_path)

    # Vain oikealle spine.json-projektille.
    if spine_path.name != "spine.json":
        return

    docs_dir = spine_path.parent / "docs"
    roadmap_path = docs_dir / "ROADMAP.md"

    docs_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    roadmap_path.write_text(
        roadmap_markdown(data),
        encoding="utf-8"
    )


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

        update_roadmap_document(
            path,
            data
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
