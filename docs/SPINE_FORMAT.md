# Spine project format

Spine projects store their project tree in a `spine.json` file in the project root.

## Root structure

Spine HUD v0.2 uses these root fields:

- `project` — project name
- `tree` — project task tree

## Task nodes

Task and branch nodes use:

- `id` — persistent task identifier
- `name` — task or branch name
- `order` — ordering value
- `paths` — files associated with the task
- `status` — task status
- `children` — child nodes

## Status values

Spine HUD v0.2 currently uses:

- `planned`
- `done`
- `blocked`

Do not infer status values only from `docs/ROADMAP.md`.

The project's `spine.json` is the source of truth.

## Paths

`paths` associates files with a task.

It may be empty when a new idea or task is created. The affected files do not need to be known in advance.

## Branches

Branches use the same node structure and contain other nodes in `children`.

A parent status displayed by Spine may be calculated from its children.

## Example project

See `examples/spine.json`.

## Integration guidance

When modifying an existing Spine project:

- preserve existing task IDs
- preserve unknown fields
- preserve task ordering
- do not require `paths` when creating an idea
- use the existing `spine.json` as the primary source of truth
