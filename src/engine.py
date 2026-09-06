import json
import subprocess
from pathlib import Path


def run_git(project_path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(project_path), *args],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return ""

    return result.stdout.strip()


def get_changed_files(project_path: Path) -> list[str]:
    output = run_git(project_path, "status", "--porcelain")

    changed = []

    for line in output.splitlines():
        if not line.strip():
            continue

        path = line[3:].strip()

        if " -> " in path:
            path = path.split(" -> ", 1)[1]

        changed.append(path)

    return changed


def path_matches(task_path: str, changed_file: str) -> bool:
    task_path = task_path.rstrip("/")

    if changed_file == task_path:
        return True

    return changed_file.startswith(task_path + "/")


def task_git_files(task: dict, changed_files: list[str]) -> list[str]:
    matches = []

    for task_path in task.get("paths", []):
        for changed in changed_files:
            if path_matches(task_path, changed):
                matches.append(changed)

    return sorted(set(matches))


def walk_tree(nodes: list[dict], changed_files: list[str]):
    result = []

    for node in nodes:
        item = {
            "name": node.get("name", "Unnamed"),
            "status": node.get("status", "idle"),
            "git_files": task_git_files(node, changed_files),
            "children": [],
        }

        children = node.get("children", [])

        if children:
            item["children"] = walk_tree(children, changed_files)

        result.append(item)

    return result


def load_spine(project_path: Path) -> dict:
    spine_file = project_path / "spine.json"

    data = json.loads(
        spine_file.read_text(encoding="utf-8")
    )

    changed_files = get_changed_files(project_path)

    return {
        "project": data.get("project", project_path.name),
        "changed_files": changed_files,
        "tree": walk_tree(
            data.get("tree", []),
            changed_files,
        ),
    }


if __name__ == "__main__":
    project = Path(__file__).resolve().parent.parent

    state = load_spine(project)

    print(f"\nSPINE: {state['project']}")
    print("\nChanged files:")

    for file in state["changed_files"]:
        print(f"  {file}")

    print("\nTask mapping:")

    def print_nodes(nodes, depth=0):
        for node in nodes:
            indent = "  " * depth

            git = ""

            if node["git_files"]:
                git = f"  [git M{len(node['git_files'])}]"

            print(
                f"{indent}- {node['name']}{git}"
            )

            print_nodes(
                node["children"],
                depth + 1,
            )

    print_nodes(state["tree"])
# test
# git live test

MAX_TASK_NAME = 80
MAX_DEPTH = 8
MAX_CHILDREN = 200
MAX_PATHS = 100
MAX_PATH_LENGTH = 300
MAX_ORDER = 1_000_000

VALID_STATUSES = {
    "planned",
    "active",
    "done",
    "blocked",
    "idle",
}


def calculated_status(node):
    children = node.get("children", [])

    if not children:
        return node.get("status", "planned")

    statuses = [
        calculated_status(child)
        for child in children
    ]

    if "blocked" in statuses:
        return "blocked"

    if "active" in statuses:
        return "active"

    if statuses and all(
        status == "done"
        for status in statuses
    ):
        return "done"

    return "planned"


class SpineValidationError(ValueError):
    pass


def validate_task_name(name: str) -> str:
    if not isinstance(name, str):
        raise SpineValidationError("Task name must be text.")

    name = name.strip()

    if not name:
        raise SpineValidationError("Task name cannot be empty.")

    if len(name) > MAX_TASK_NAME:
        raise SpineValidationError(
            f"Task name can be at most {MAX_TASK_NAME} characters."
        )

    if "\n" in name or "\r" in name or "\t" in name:
        raise SpineValidationError(
            "Task name cannot contain line breaks or tabs."
        )

    return name


def validate_tree(nodes, depth=1, seen_ids=None):
    if seen_ids is None:
        seen_ids = set()

    if depth > MAX_DEPTH:
        raise SpineValidationError(
            f"Tree can be at most {MAX_DEPTH} levels deep."
        )

    if not isinstance(nodes, list):
        raise SpineValidationError("Tree children must be a list.")

    if len(nodes) > MAX_CHILDREN:
        raise SpineValidationError(
            f"A branch can contain at most {MAX_CHILDREN} children."
        )

    sibling_names = set()

    for node in nodes:
        if not isinstance(node, dict):
            raise SpineValidationError("Every task must be an object.")

        name = validate_task_name(node.get("name", ""))

        name_key = name.casefold()

        if name_key in sibling_names:
            raise SpineValidationError(
                f'Duplicate task name under same branch: "{name}"'
            )

        sibling_names.add(name_key)

        status = node.get("status", "planned")

        if status not in VALID_STATUSES:
            raise SpineValidationError(
                f'Invalid status "{status}" for "{name}".'
            )

        order = node.get("order")

        if order is not None:
            if not isinstance(order, int):
                raise SpineValidationError(
                    f'Order for "{name}" must be an integer.'
                )

            if order < 0 or order > MAX_ORDER:
                raise SpineValidationError(
                    f'Order for "{name}" is outside allowed range.'
                )

        node_id = node.get("id")

        if node_id is not None:
            if not isinstance(node_id, str):
                raise SpineValidationError(
                    f'ID for "{name}" must be text.'
                )

            if len(node_id) > 120:
                raise SpineValidationError(
                    f'ID for "{name}" is too long.'
                )

            if node_id in seen_ids:
                raise SpineValidationError(
                    f'Duplicate task ID: "{node_id}"'
                )

            seen_ids.add(node_id)

        paths = node.get("paths", [])

        if not isinstance(paths, list):
            raise SpineValidationError(
                f'Paths for "{name}" must be a list.'
            )

        if len(paths) > MAX_PATHS:
            raise SpineValidationError(
                f'"{name}" has too many paths.'
            )

        for item in paths:
            if not isinstance(item, str):
                raise SpineValidationError(
                    f'Path in "{name}" must be text.'
                )

            if len(item) > MAX_PATH_LENGTH:
                raise SpineValidationError(
                    f'Path in "{name}" is too long.'
                )

        validate_tree(
            node.get("children", []),
            depth + 1,
            seen_ids
        )


def validate_spine_data(data: dict):
    if not isinstance(data, dict):
        raise SpineValidationError(
            "Spine configuration must be an object."
        )

    project = data.get("project", "")

    if not isinstance(project, str):
        raise SpineValidationError(
            "Project name must be text."
        )

    if len(project.strip()) > 100:
        raise SpineValidationError(
            "Project name is too long."
        )

    validate_tree(data.get("tree", []))

    return True
