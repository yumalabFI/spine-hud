import json
import os
import tempfile
from pathlib import Path

try:
    from .runtime_env import CONFIG_DIR
except ImportError:
    from runtime_env import CONFIG_DIR


PROJECTS_FILE = CONFIG_DIR / "projects.json"


class ProjectRegistryError(RuntimeError):
    pass


def load_projects() -> dict:
    if not PROJECTS_FILE.exists():
        return {
            "projects": [],
            "ignored": [],
            "last_opened": None,
        }

    try:
        data = json.loads(
            PROJECTS_FILE.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectRegistryError(
            f"Cannot read project registry: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ProjectRegistryError(
            "Project registry must be an object."
        )

    projects = data.get("projects", [])
    ignored = data.get("ignored", [])
    last_opened = data.get("last_opened")

    if not isinstance(projects, list):
        raise ProjectRegistryError(
            "projects must be a list."
        )

    if not isinstance(ignored, list):
        raise ProjectRegistryError(
            "ignored must be a list."
        )

    return {
        "projects": projects,
        "ignored": ignored,
        "last_opened": last_opened,
    }


def save_projects(data: dict) -> None:
    CONFIG_DIR.mkdir(
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
            dir=CONFIG_DIR,
            prefix=".projects.",
            suffix=".tmp",
            delete=False,
        ) as temp:
            temp.write(content)
            temp.flush()
            os.fsync(temp.fileno())
            temp_path = Path(temp.name)

        os.replace(
            temp_path,
            PROJECTS_FILE
        )

    except OSError as exc:
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass

        raise ProjectRegistryError(
            f"Cannot save project registry: {exc}"
        ) from exc


def add_project(path: Path) -> dict:
    path = Path(path).expanduser().resolve()

    spine_file = path / "spine.json"

    if not spine_file.exists():
        raise ProjectRegistryError(
            f"No spine.json found in {path}"
        )

    try:
        spine_data = json.loads(
            spine_file.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectRegistryError(
            f"Cannot read project: {exc}"
        ) from exc

    name = spine_data.get(
        "project",
        path.name
    )

    data = load_projects()

    path_text = str(path)

    existing = next(
        (
            project
            for project in data["projects"]
            if project.get("path") == path_text
        ),
        None
    )

    if existing is None:
        project = {
            "name": name,
            "path": path_text,
        }

        data["projects"].append(project)
    else:
        existing["name"] = name
        project = existing

    save_projects(data)

    return project


def ignore_project(path: Path) -> None:
    path_text = str(
        Path(path).expanduser().resolve()
    )

    data = load_projects()

    if path_text in {
        project.get("path")
        for project in data.get("ignored", [])
    }:
        return

    data["ignored"].append({
        "path": path_text
    })

    save_projects(data)


def rename_project(path: Path, new_name: str) -> dict:
    path_text = str(
        Path(path).expanduser().resolve()
    )

    new_name = new_name.strip()

    if not new_name:
        raise ProjectRegistryError(
            "Project name cannot be empty."
        )

    if len(new_name) > 80:
        raise ProjectRegistryError(
            "Project name is too long."
        )

    data = load_projects()

    for project in data["projects"]:
        if project.get("path") == path_text:
            project["name"] = new_name
            save_projects(data)
            return project

    raise ProjectRegistryError(
        f"Project is not registered: {path}"
    )


def remove_project(path: Path) -> bool:
    path_text = str(
        Path(path).expanduser().resolve()
    )

    data = load_projects()

    before = len(data["projects"])

    data["projects"] = [
        project
        for project in data["projects"]
        if project.get("path") != path_text
    ]

    changed = (
        len(data["projects"]) != before
    )

    if data.get("last_opened") == path_text:
        data["last_opened"] = None

    if changed:
        save_projects(data)

    return changed


def set_last_opened(path: Path) -> None:
    path_text = str(
        Path(path).expanduser().resolve()
    )

    data = load_projects()
    data["last_opened"] = path_text
    save_projects(data)
