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
