import json
import sys
from pathlib import Path

PROJECT = Path.cwd()
SPINE_FILE = PROJECT / "spine.json"


def load():
    if not SPINE_FILE.exists():
        print("No spine.json found.")
        sys.exit(1)

    return json.loads(SPINE_FILE.read_text(encoding="utf-8"))


def save(data):
    SPINE_FILE.write_text(
        json.dumps(data, indent=2) + "\n",
        encoding="utf-8"
    )


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


def command_status(data):
    print(f"\nSPINE — {data.get('project', PROJECT.name)}\n")

    def show(nodes, depth=0):
        for task in nodes:
            status = task.get("status", "planned")

            icon = {
                "done": "✓",
                "active": "●",
                "blocked": "!",
                "planned": "○",
                "idle": "○",
            }.get(status, "○")

            print(
                f"{'  ' * depth}{icon} {task.get('name')}"
            )

            show(
                task.get("children", []),
                depth + 1
            )

    show(data.get("tree", []))


def main():
    data = load()

    if len(sys.argv) == 1:
        command_status(data)
        return

    if sys.argv[1] == "status":
        command_status(data)
        return

    if sys.argv[1] == "next":
        command_next(data)
        return

    if len(sys.argv) < 3:
        print(
            "Commands:\n"
            "  spine status\n"
            "  spine next\n"
            "  spine <task> start\n"
            "  spine <task> done\n"
            "  spine <task> block"
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
