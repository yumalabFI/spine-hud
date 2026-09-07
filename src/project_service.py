from pathlib import Path

try:
    from .cli import command_init
    from .project_registry import (
        add_project,
        load_projects,
        rename_project,
        remove_project,
    )
    from .project_scanner import scan_git_projects
except ImportError:
    from cli import command_init
    from project_registry import (
        add_project,
        load_projects,
        rename_project,
        remove_project,
    )
    from project_scanner import scan_git_projects


def register_existing_project(path):
    path = Path(path).expanduser().resolve()
    return add_project(path)


def create_new_project(path):
    path = Path(path).expanduser().resolve()

    if path.exists():
        raise FileExistsError(
            f"Project folder already exists: {path}"
        )

    command_init(path)
    return register_existing_project(path)


def initialize_existing_project(path):
    path = Path(path).expanduser().resolve()
    command_init(path)
    return register_existing_project(path)


def load_project_registry():
    return load_projects()


def scan_projects(roots=None, max_depth=4):
    return scan_git_projects(
        roots=roots,
        max_depth=max_depth,
    )


def rename_existing_project(path, new_name):
    return rename_project(path, new_name)


def remove_existing_project(path):
    return remove_project(path)
