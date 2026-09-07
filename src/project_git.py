import subprocess
from pathlib import Path


def git_project_info(path: Path) -> dict:
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(path),
                "status",
                "--short",
            ],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )

        lines = [
            line
            for line in result.stdout.splitlines()
            if line.strip()
        ]

        modified = 0
        untracked = 0
        staged = 0

        for line in lines:
            if line.startswith("??"):
                untracked += 1
                continue

            if len(line) >= 2:
                if line[0] != " ":
                    staged += 1

                if line[1] != " ":
                    modified += 1

        if not lines:
            status = "CLEAN"
        else:
            parts = []

            if staged:
                parts.append(
                    f"{staged} staged"
                )

            if modified:
                parts.append(
                    f"{modified} modified"
                )

            if untracked:
                parts.append(
                    f"{untracked} untracked"
                )

            status = " · ".join(parts)

        commit_result = subprocess.run(
            [
                "git",
                "-C",
                str(path),
                "log",
                "-1",
                "--format=%cs",
            ],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )

        last_commit = (
            commit_result.stdout.strip()
            or None
        )

        return {
            "status": status,
            "last_commit": last_commit,
        }

    except (
        OSError,
        subprocess.SubprocessError,
    ):
        return {
            "status": "GIT ERROR",
            "last_commit": None,
        }
