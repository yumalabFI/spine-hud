import json
import os
from pathlib import Path

try:
    from .project_registry import load_projects
    from .project_git import git_project_info
except ImportError:
    from project_registry import load_projects
    from project_git import git_project_info


def scan_git_projects(
    roots=None,
    max_depth=4
) -> list[dict]:
    if roots is None:
        roots = [Path.home()]

    registry = load_projects()

    registered = {
        str(Path(project.get("path")).expanduser().resolve())
        for project in registry.get("projects", [])
        if project.get("path")
    }

    ignored = {
        str(Path(project.get("path")).expanduser().resolve())
        for project in registry.get("ignored", [])
        if project.get("path")
    }

    found = []
    visited = set()

    skip_dirs = {
        ".cache",
        ".local",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".tox",
        ".pytest_cache",
    }

    for root in roots:
        root = Path(root).expanduser().resolve()

        if not root.exists() or not root.is_dir():
            continue

        try:
            walker = os.walk(
                root,
                topdown=True,
                onerror=lambda exc: None
            )

            for current, dirs, files in walker:
                current_path = Path(current)

                try:
                    relative = current_path.relative_to(root)
                    depth = len(relative.parts)
                except ValueError:
                    dirs[:] = []
                    continue

                # Älä kulje tarpeettomiin raskaisiin hakemistoihin.
                dirs[:] = [
                    name
                    for name in dirs
                    if name not in skip_dirs
                ]

                if depth >= max_depth:
                    dirs[:] = [
                        name
                        for name in dirs
                        if name == ".git"
                    ]

                # Projekti tunnistetaan Git-reposta.
                if ".git" not in dirs:
                    continue

                try:
                    project_path = current_path.resolve()
                except OSError:
                    dirs[:] = []
                    continue

                # Älä skannaa projektin sisälle enää.
                dirs[:] = []

                path_text = str(project_path)

                if path_text in visited:
                    continue

                visited.add(path_text)

                if path_text in registered:
                    continue

                if path_text in ignored:
                    continue

                spine_file = project_path / "spine.json"
                has_spine = spine_file.exists()

                name = project_path.name

                if has_spine:
                    try:
                        data = json.loads(
                            spine_file.read_text(
                                encoding="utf-8"
                            )
                        )
                    except (OSError, json.JSONDecodeError):
                        # Rikkinäistä spine.json:ia ei alusteta
                        # vahingossa uudelleen.
                        continue

                    name = data.get(
                        "project",
                        project_path.name
                    )

                git_info = git_project_info(
                    project_path
                )

                found.append({
                    "name": name,
                    "path": path_text,
                    "has_spine": has_spine,
                    "git_status": git_info["status"],
                    "last_commit": git_info["last_commit"],
                })

        except OSError:
            continue

    return sorted(
        found,
        key=lambda project: (
            project["name"].lower(),
            project["path"].lower(),
        )
    )
