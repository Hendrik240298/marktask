# MarkTask implementation plan

Date: 2026-09-28  
Status: read-only MVP plus opt-in, guarded single-task editing implemented; real-vault write trial still pending.

## Goal and boundary

Make the questions in [MANIFEST.md](MANIFEST.md) answerable from local Markdown: what is due today or soon, what is overdue or waiting, and which project a task belongs to. Start with a **read-only** Python/Dash interface; Markdown remains the sole source of truth. No import, migration, remote service, or automatic edits to the input files.

The input is **one user-supplied Projects directory**, not a hard-coded vault or this repository. During development, use `1-Projects/` here as a sample. Later the same entry point should accept the real directory, for example:

```sh
marktask --projects-dir /path/to/real/1-Projects
```

The CLI must check that the path exists and is a directory, and report actionable errors. It must not assume that the input is next to the package, require an Obsidian vault root, or silently fall back to the sample. Keep input content out of any generated index, logs, or repository changes unless explicitly requested; do not copy the real vault into the app. For tests, use a tiny synthetic fixture in addition to opt-in checks against the sample.

## What the sample establishes

- `1-Projects/` contains project folders, nested subprojects and some loose Markdown files. Define a clear policy for loose files (an unassigned/root bucket) and attach nested tasks to their top-level project while preserving their relative source path.
- Tasks occur in ordinary notes, not only in Kanban files.
- Obsidian Kanban boards use `kanban-plugin: board`, `##` columns and standard checkboxes; the local development sample includes empty and populated boards. Synthetic integration tests cover both without committing the sample.
- Column names may include `In Process`, `ToDo`, `Doing`, `Doing - Personal`, `Review`, `Backlog`, `Waiting`, and `Done`. Do not impose the manifest's suggested default columns on existing boards. Preserve the raw column name and, only when configured, map aliases to global statuses.
- Some task lines contain Obsidian wikilinks, block IDs, `✅ YYYY-MM-DD`, `📅 YYYY-MM-DD`, tags, indentation, or nested checkboxes. Ignore frontmatter, fenced code, and Kanban settings as task sources. Keep the original text and source location even if a metadata token is unsupported; emit a warning rather than fabricating a date or changing a file.
- The sample is a development fixture, not the canonical data or a reason to commit its contents. Review its provenance and sensitivity before any future `git add` or publication.

## Delivery sequence

### 1. Contract and discovery CLI

Define and document the supported task grammar: `- [ ]` / `- [x]` (also `[X]`), optional `📅 YYYY-MM-DD`, optional `🔁` text, tags and a Kanban `##` heading. Treat unsupported recurrence rules as display-only until implemented. Decide whether project frontmatter `due` is shown separately from task due dates; do not conflate them. Start with a compact Python package (`pyproject.toml`, `src/marktask/`, `tests/`, `README.md`); split modules only when the code needs it.

Implement `marktask scan --projects-dir PATH` to discover `.md` files recursively under that exact directory, with explicit configurable exclusions and a conservative symlink policy (do not follow directory symlinks by default). Output counts and diagnostics with relative paths, not full note contents. One malformed file must not abort all other files.

**Done when:** the sample scans without writing to it; invalid/missing paths fail clearly; exclusions and loose/nested files are covered by tests.

### 2. Read-only task index

Extract task lines with a small, tested parser, carrying `project`, raw/status alias, completion, due date, raw recurrence, tags, relative source path, line number and original line. Avoid persistent IDs for read-only views; line numbers are locations, not stable identities. Parse valid ISO dates, report invalid ones, and keep unknown syntax intact. Index in memory, rebuilt from source on demand; no SQLite or background watcher yet.

**Done when:** synthetic tests cover fenced examples, frontmatter, nested tasks, Unicode, empty boards, mixed text, malformed dates, unsupported recurrence, and duplicate-looking tasks; a sample scan produces checkable counts and source references.

### 3. Local read-only dashboard

Add a minimal Dash app bound to `127.0.0.1`, with manual refresh, project overview, Today, Overdue, Upcoming and Waiting lists, plus basic search/filtering. Base dates on the user's local day; define whether Upcoming excludes Today and Overdue. Show each item's relative source path and line number, with a copy/open affordance that works without assuming a browser can open `file://` links. No write controls or server exposure to the LAN.

**Done when:** `marktask serve --projects-dir PATH` works on the sample and then an arbitrary chosen Projects directory with no code changes; dashboard filters and counts match the CLI index; edits made in a Markdown editor appear after refresh; the app leaves the input unchanged.

### 4. Only after read-only validation: controlled writes

Follow the focused [editing plan](EDITING_PLAN.md) for guarded snapshot handles, conflict detection, minimal edits, line-ending preservation, atomic replacement, UI confirmation and recovery before enabling complete/reopen or due-date changes. Test with temporary files and external edits; never first test write operations against the real directory. Persistent IDs are deferred until move/recurrence workflows. Later add completion-triggered recurrence with idempotency, then Kanban moves and optional notifications. None of these are MVP requirements.

## Decisions to validate before implementation

1. Input shape: direct path to `1-Projects/` (proposed) versus vault root plus a `1-Projects` setting. Support the former first because it is the promised user workflow.
2. Project scope: direct children are projects; loose files go into a visible root bucket; nested folders stay within the top-level project. Decide whether `_Mabye or Later` and `_One Action Projects` should be excluded or shown as projects; don't guess from their names.
3. Status: retain arbitrary Kanban column labels, with optional alias mapping for aggregate Waiting/In Progress views. A plain note without a Kanban column has no inferred Kanban status.
4. Recurrence: recognize `🔁` in the index, but do not generate tasks until writes and an idempotency policy exist.
5. Packaging/privacy: initialize Git locally without a remote; do not stage or commit the bundled sample or a real vault by default. Before first commit, decide whether to replace the sample with small sanitized fixtures or keep it outside version control.

## Scope guard

No initial dependency on Obsidian plugins, pandas, SQLite, file watchers, scheduled jobs, AI, or notification services. Dash is only an interface. The strongest acceptance test is that the same read-only command works when pointed at the real Projects directory, while the Markdown remains usable without MarkTask.
