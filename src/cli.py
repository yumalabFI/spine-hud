import json
import sys
import uuid
from pathlib import Path

from engine import (
    get_changed_files,
    get_last_commit,
    path_matches,
    task_git_state,
)

from storage import (
    SpineStorageError,
    load_spine,
    save_spine,
    roadmap_markdown,
)

PROJECT = Path.cwd()
SPINE_FILE = PROJECT / "spine.json"


def load():
    if not SPINE_FILE.exists():
        print("No spine.json found.")
        sys.exit(1)

    try:
        return load_spine(SPINE_FILE)
    except SpineStorageError as exc:
        print(f"Spine error: {exc}")
        sys.exit(1)


def save(data):
    try:
        save_spine(
            SPINE_FILE,
            data
        )
    except SpineStorageError as exc:
        print(f"Spine error: {exc}")
        sys.exit(1)


def all_tasks(nodes):
    for node in nodes:
        yield node

        for child in all_tasks(node.get("children", [])):
            yield child


def leaf_tasks(nodes):
    for node in nodes:
        children = node.get("children", [])

        if children:
            yield from leaf_tasks(children)
        else:
            yield node


def find_task(data, query):
    query = query.lower()

    exact = []
    partial = []

    for task in all_tasks(data.get("tree", [])):
        name = task.get("name", "")

        if name.lower() == query:
            exact.append(task)
        elif query in name.lower():
            partial.append(task)

    if len(exact) == 1:
        return exact[0]

    if len(partial) == 1:
        return partial[0]

    if len(partial) > 1:
        print("Multiple tasks match:")
        for task in partial:
            print(" -", task["name"])
        sys.exit(1)

    print(f'Task not found: "{query}"')
    sys.exit(1)


def clear_active(nodes):
    for task in all_tasks(nodes):
        if task.get("status") == "active":
            task["status"] = "planned"


def activate_next(data):
    # If something is already active, keep it.
    for task in leaf_tasks(data.get("tree", [])):
        if task.get("status") == "active":
            return task

    # Otherwise activate the first unfinished task in tree order.
    for task in leaf_tasks(data.get("tree", [])):
        status = task.get("status", "planned")

        if status in ("planned", "idle"):
            task["status"] = "active"
            return task

    return None


def command_start(data, task_name):
    task = find_task(data, task_name)

    clear_active(data["tree"])
    task["status"] = "active"

    save(data)

    print(f"● ACTIVE: {task['name']}")


def command_done(data, task_name):
    task = find_task(data, task_name)

    task["status"] = "done"

    next_task = activate_next(data)

    save(data)

    print(f"✓ DONE: {task['name']}")

    if next_task:
        print(f"● NEXT: {next_task['name']}")
    else:
        print("✓ PROJECT COMPLETE")


def command_block(data, task_name):
    task = find_task(data, task_name)

    task["status"] = "blocked"

    clear_active(data["tree"])
    next_task = activate_next(data)

    save(data)

    print(f"! BLOCKED: {task['name']}")

    if next_task:
        print(f"● NEXT: {next_task['name']}")


def command_next(data):
    next_task = activate_next(data)

    save(data)

    if next_task:
        print(f"● ACTIVE: {next_task['name']}")
    else:
        print("✓ PROJECT COMPLETE")







def command_init(project_path=None):
    if project_path:
        project = Path(project_path).expanduser().resolve()
    else:
        project = Path.cwd()

    spine_file = project / "spine.json"

    if spine_file.exists():
        print(f"spine.json already exists: {spine_file}")
        sys.exit(1)

    project.mkdir(
        parents=True,
        exist_ok=True
    )

    def node(name, order):
        return {
            "id": f"task-{uuid.uuid4().hex[:12]}",
            "name": name,
            "status": "planned",
            "order": order,
            "paths": [],
            "children": []
        }

    roadmap = node("Roadmap", 10)
    version = node("v0.1", 10)

    version["children"] = [
        node("Core", 10),
        node("UI", 20),
        node("Integration", 30),
        node("Tests", 40),
        node("Docs", 50),
        node("Release", 60),
    ]

    roadmap["children"] = [version]

    data = {
        "project": project.name,
        "tree": [roadmap]
    }

    try:
        save_spine(
            spine_file,
            data
        )
    except SpineStorageError as exc:
        print(f"Spine error: {exc}")
        sys.exit(1)

    print(
        f"✓ Spine project initialized: {project}"
    )
    print(
        f"✓ Created: {spine_file}"
    )


def command_remove(data, task_name):
    task = find_task(data, task_name)

    task_id = task.get("id")

    if not task_id:
        print("Remove requires persistent task ID.")
        sys.exit(1)

    answer = input(
        f'Remove "{task["name"]}" and everything under it? [y/N]: '
    ).strip().lower()

    if answer not in ("y", "yes"):
        print("Cancelled.")
        return

    removed = False

    def remove_from(nodes):
        nonlocal removed

        for index, node in enumerate(nodes):
            if node.get("id") == task_id:
                del nodes[index]
                removed = True
                return True

            if remove_from(node.get("children", [])):
                return True

        return False

    remove_from(data.get("tree", []))

    if not removed:
        print("Remove failed: task not found.")
        sys.exit(1)

    save(data)

    print(f'✓ REMOVED: {task["name"]}')


def command_rename(data, old_name, new_name):
    task = find_task(data, old_name)

    new_name = new_name.strip()

    if not new_name:
        print("Task name cannot be empty.")
        sys.exit(1)

    if len(new_name) > 80:
        print("Task name can be at most 80 characters.")
        sys.exit(1)

    parent_list = None

    def find_parent_list(nodes):
        nonlocal parent_list

        for node in nodes:
            if node is task:
                parent_list = nodes
                return True

            if find_parent_list(node.get("children", [])):
                return True

        return False

    find_parent_list(data.get("tree", []))

    if parent_list is None:
        print("Rename failed: parent not found.")
        sys.exit(1)

    for node in parent_list:
        if node is task:
            continue

        if node.get("name", "").casefold() == new_name.casefold():
            print(
                f'Task already exists under this branch: "{new_name}"'
            )
            sys.exit(1)

    old = task.get("name", "")
    task["name"] = new_name

    save(data)

    print(f'✓ RENAMED: {old} -> {new_name}')


def command_add(data, task_name, parent_name=None):
    task_name = task_name.strip()

    if not task_name:
        print("Task name cannot be empty.")
        sys.exit(1)

    if len(task_name) > 80:
        print("Task name can be at most 80 characters.")
        sys.exit(1)

    new_task = {
        "id": f"task-{uuid.uuid4().hex[:12]}",
        "name": task_name,
        "status": "planned",
        "paths": []
    }

    if parent_name is None:
        target_list = data.setdefault("tree", [])
    else:
        parent = find_task(data, parent_name)
        target_list = parent.setdefault("children", [])

    # Duplicate saman parentin alla
    if any(
        node.get("name", "").casefold()
        == task_name.casefold()
        for node in target_list
    ):
        print(
            f'Task already exists under this branch: "{task_name}"'
        )
        sys.exit(1)

    new_task["order"] = (
        max(
            (
                node.get("order", 0)
                for node in target_list
            ),
            default=0
        )
        + 10
    )

    target_list.append(new_task)

    save(data)

    if parent_name:
        print(
            f'✓ ADDED: {task_name} under {parent_name}'
        )
    else:
        print(
            f'✓ ADDED: {task_name}'
        )


def command_move(data, task_name, relation, target_name):
    task = find_task(data, task_name)
    target = find_task(data, target_name)

    task_id = task.get("id")
    target_id = target.get("id")

    if not task_id or not target_id:
        print("Move requires persistent task IDs.")
        sys.exit(1)

    if task_id == target_id:
        print("Task cannot be moved relative to itself.")
        sys.exit(1)

    descendant_ids = set()

    def collect_descendants(node):
        for child in node.get("children", []):
            child_id = child.get("id")
            if child_id:
                descendant_ids.add(child_id)
            collect_descendants(child)

    collect_descendants(task)

    if target_id in descendant_ids:
        print("Task cannot be moved under or relative to its own child.")
        sys.exit(1)

    source_list = None
    source_index = None
    target_list = None
    target_index = None

    def locate(nodes):
        nonlocal source_list, source_index
        nonlocal target_list, target_index

        for index, node in enumerate(nodes):
            node_id = node.get("id")

            if node_id == task_id:
                source_list = nodes
                source_index = index

            if node_id == target_id:
                target_list = nodes
                target_index = index

            locate(node.get("children", []))

    locate(data.get("tree", []))

    if source_list is None or target_list is None:
        print("Move failed: task location not found.")
        sys.exit(1)

    moved = source_list.pop(source_index)

    if relation == "--under":
        target_children = target.setdefault("children", [])
        target_children.append(moved)

        for index, node in enumerate(source_list, start=1):
            node["order"] = index * 10

        for index, node in enumerate(target_children, start=1):
            node["order"] = index * 10

    elif relation in ("--before", "--after"):
        # Jos task ja target olivat samassa listassa,
        # targetin indeksi voi muuttua popin jälkeen.
        target_list = None
        target_index = None

        def relocate_target(nodes):
            nonlocal target_list, target_index

            for index, node in enumerate(nodes):
                if node.get("id") == target_id:
                    target_list = nodes
                    target_index = index
                    return True

                if relocate_target(node.get("children", [])):
                    return True

            return False

        relocate_target(data.get("tree", []))

        if target_list is None:
            print("Move failed: target disappeared.")
            sys.exit(1)

        insert_index = target_index

        if relation == "--after":
            insert_index += 1

        target_list.insert(insert_index, moved)

        affected = {id(source_list): source_list, id(target_list): target_list}

        for nodes in affected.values():
            for index, node in enumerate(nodes, start=1):
                node["order"] = index * 10

    else:
        print("Move relation must be --under, --before or --after.")
        sys.exit(1)

    save(data)

    print(
        f'✓ MOVED: {task["name"]} '
        f'{relation} {target["name"]}'
    )



def command_roadmap(data, output_path=None):
    if output_path:
        output = Path(output_path)
    else:
        output = PROJECT / "docs" / "ROADMAP.md"

    output.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    output.write_text(
        roadmap_markdown(data),
        encoding="utf-8"
    )

    print(
        f"✓ Roadmap generated: {output}"
    )


def command_status(data):
    print(f"\nSPINE — {data.get('project', PROJECT.name)}\n")

    changed_files = get_changed_files(PROJECT)

    commit = get_last_commit(PROJECT)
    commit_files = (
        commit.get("files", [])
        if commit
        else []
    )

    def show(nodes, depth=0):
        for task in nodes:
            status = task.get(
                "status",
                "planned"
            )

            icon = {
                "done": "✓",
                "active": "●",
                "blocked": "!",
                "planned": "○",
                "idle": "○",
            }.get(status, "○")

            git_text = ""

            # Näytä Git vain leaf-taskille.
            if not task.get("children"):
                state = task_git_state(
                    task,
                    changed_files,
                    commit_files
                )

                if status == "active":
                    if state["changed"]:
                        git_text = (
                            f"   M{len(state['changed'])}"
                        )

                    elif state["ready"]:
                        git_text = "   READY?"

                elif (
                    status == "done"
                    and state["committed"]
                ):
                    git_text = "   C"

            print(
                f"{'  ' * depth}"
                f"{icon} {task.get('name')}"
                f"{git_text}"
            )

            show(
                task.get("children", []),
                depth + 1
            )

    show(data.get("tree", []))


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "init":
        if len(sys.argv) == 2:
            command_init()

        elif len(sys.argv) == 3:
            command_init(
                sys.argv[2]
            )

        else:
            print(
                "Usage:\n"
                "  spine init\n"
                "  spine init /path/to/project"
            )

        return

    data = load()

    if len(sys.argv) == 1:
        command_status(data)
        return

    if sys.argv[1] == "roadmap":
        if len(sys.argv) == 2:
            command_roadmap(data)
        elif len(sys.argv) == 3:
            command_roadmap(
                data,
                sys.argv[2]
            )
        else:
            print(
                "Usage:\n"
                "  spine roadmap\n"
                "  spine roadmap /path/to/ROADMAP.md"
            )
        return

    if sys.argv[1] == "status":
        command_status(data)
        return

    if sys.argv[1] == "next":
        command_next(data)
        return

    if sys.argv[1] == "remove":
        if len(sys.argv) != 3:
            print(
                'Usage:\n'
                '  spine remove "task"'
            )
            return

        command_remove(
            data,
            sys.argv[2]
        )
        return

    if sys.argv[1] == "rename":
        if len(sys.argv) != 4:
            print(
                'Usage:\n'
                '  spine rename "old name" "new name"'
            )
            return

        command_rename(
            data,
            sys.argv[2],
            sys.argv[3]
        )
        return

    if sys.argv[1] == "add":
        if len(sys.argv) == 3:
            command_add(
                data,
                sys.argv[2]
            )
            return

        if (
            len(sys.argv) == 5
            and sys.argv[3] == "--under"
        ):
            command_add(
                data,
                sys.argv[2],
                sys.argv[4]
            )
            return

        print(
            'Usage:\n'
            '  spine add "task"\n'
            '  spine add "task" --under "branch"'
        )
        return

    if sys.argv[1] == "move":
        if len(sys.argv) != 5:
            print(
                'Usage:\n'
                '  spine move "task" --under "branch"\n'
                '  spine move "task" --before "task"\n'
                '  spine move "task" --after "task"'
            )
            return

        command_move(
            data,
            sys.argv[2],
            sys.argv[3],
            sys.argv[4]
        )
        return

    if len(sys.argv) < 3:
        print(
            "Commands:\n"
            "  spine status\n"
            "  spine next\n"
            "  spine <task> start\n"
            "  spine <task> done\n"
            "  spine <task> block\n"
            '  spine move "task" --under "branch"\n'
            '  spine move "task" --before "task"\n'
            '  spine move "task" --after "task"'
        )
        return

    task_name = sys.argv[1]
    action = sys.argv[2]

    if action == "start":
        command_start(data, task_name)

    elif action == "done":
        command_done(data, task_name)

    elif action == "block":
        command_block(data, task_name)

    else:
        print(f"Unknown action: {action}")


if __name__ == "__main__":
    main()
