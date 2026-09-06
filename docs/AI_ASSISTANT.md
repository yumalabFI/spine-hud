# Spine AI Assistant Guide

This document is an operating protocol for AI coding assistants working in a project that uses Spine.

Spine is the project's shared roadmap and work-state system.

The authoritative project state is `spine.json`.

`docs/ROADMAP.md` is generated from that state and must not be maintained manually.

---

## First action in every session

Before changing code, inspect Spine:

    spine status

Use the result to understand:

- the project structure
- completed work
- planned work
- blocked work
- the currently active task

Do not assume the conversation alone represents the current project state.

---

# Mode A — Existing Spine project

If `spine.json` already contains a meaningful project roadmap:

1. Run:

       spine status

2. Find the active task.

3. If a task is already active, continue that work unless the developer asks for something else.

4. If the requested work is not represented in Spine, add it to the appropriate branch.

5. Before beginning a planned task:

       spine "Task name" start

6. Keep Spine synchronized as the implementation changes.

7. Test the work before marking it complete.

8. When genuinely complete:

       spine "Task name" done

---

# Mode B — Adopt an existing project

An existing software project may already contain substantial code and Git history but have no useful Spine roadmap yet.

In this case, do not blindly use the default skeleton as the roadmap.

First inspect the project.

At minimum inspect:

- directory structure
- README and documentation
- dependency/package files
- application entry points
- important source directories
- tests
- Git working tree
- recent Git history

Useful commands include:

    git status --short
    git log --oneline --decorate -20

Then inspect enough source code to understand the major components.

## Build the roadmap from evidence

Use the repository evidence to reshape the Spine skeleton into a useful project roadmap.

The roadmap should describe:

- major existing components
- current unfinished work
- known bugs or missing pieces
- testing/stabilization work
- documentation work
- release work when relevant
- future work that is clearly supported by the project

Do not create an enormous task list from every source file.

Prefer meaningful development units.

Example:

    Roadmap
      Current release
        Core
        UI
        Storage
        Integration
        Tests
        Docs
        Release
      Later
        ...

The actual structure should follow the project, not this example.

## Existing completed work

Do not mark tasks `done` merely because they sound like something the project probably has.

Use evidence.

Evidence may include:

- existing implementation
- tests
- documentation
- Git history
- configuration
- clearly completed functionality

If completion is uncertain, prefer `planned`.

Do not fabricate historical task state.

## Current work

Inspect the working tree:

    git status --short

Use the current code, Git changes and conversation context to identify what is actually being worked on.

If a current task can be identified confidently, represent it in Spine and start it.

If several interpretations are plausible and choosing incorrectly would substantially change the roadmap, ask the developer.

## Git history

Git history is evidence about the project, not a complete task history.

Do not invent exact historical Spine states from commits.

Use commits to help understand:

- implemented features
- architecture changes
- recent work
- likely completed milestones

---

# Mode C — New project

For a new project, initialize Spine:

    spine init

The generated skeleton is only a starting structure.

Reshape it as the project becomes understood.

Do not preserve skeleton branches merely because Spine generated them.

---

# Spine commands

Inspect:

    spine status

Start:

    spine "Task name" start

Complete:

    spine "Task name" done

Block:

    spine "Task name" block

Add:

    spine add "Task name"

Add under a branch:

    spine add "Task name" --under "Branch"

Rename:

    spine rename "Old name" "New name"

Move:

    spine move "Task" --under "Branch"
    spine move "Task" --before "Other task"
    spine move "Task" --after "Other task"

Remove:

    spine remove "Task"

Removal also removes child tasks. Use it carefully.

---

# During implementation

Spine must follow the real work.

When new necessary work is discovered, add it to the roadmap instead of silently doing unrelated work.

When switching tasks, update the active task.

When work becomes blocked, mark it blocked:

    spine "Task name" block

Do not mark work complete just because code was generated.

Before `done`, verify the relevant behavior.

---

# Git indicators

Spine may display Git information beside tasks.

    M2

Two mapped files currently contain uncommitted changes.

    C

Mapped work appears in the latest commit.

    READY?

The active task appears in the latest commit and has no new mapped changes.

`READY?` is a suggestion only.

It is not proof that the implementation is correct or complete.

Testing and developer judgment still determine completion.

---

# ROADMAP.md

`docs/ROADMAP.md` is generated automatically from `spine.json`.

Do not edit it manually.

Change the project through Spine instead.

---

# Working with the developer

Do not make the developer manually maintain Spine while you are doing the implementation work.

When appropriate, run the Spine commands yourself as part of the development workflow.

Explain important roadmap changes when they affect project scope or priorities.

Do not repeatedly stop merely to report routine Spine bookkeeping.

Continue normal development until:

- the requested work is complete
- a real decision from the developer is required
- progress is blocked
- the developer asks to stop or pause

---

# Adoption completion check

When adopting Spine into an existing project, adoption is complete when:

- the repository has been inspected
- Git state has been inspected
- the skeleton has been replaced or reshaped into a meaningful roadmap
- clearly completed work is represented conservatively
- current unfinished work is represented
- the current task is active when it can be identified
- `spine status` gives a useful picture of where the project stands

After adoption, use Spine continuously rather than rebuilding the roadmap every session.

---

# Core rule

Spine must describe reality.

Do not use it to record what you merely intend to do as if it had already happened.

Inspect first, update Spine from evidence, perform the work, test it, and keep the roadmap synchronized with the actual project.
