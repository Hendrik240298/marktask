# MarkTask editing plan

Date: 2026-09-28
Status: Gates A–C implemented and expanded; a guarded Kanban move increment is implemented on synthetic files. A controlled single-line write-and-restore on a temporary note in the disposable sample copy passed previously. Interactive desktop-browser and separate real-vault move trials remain pending.

This is the detailed follow-up to [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), phase 4, and the [manifest's safe-writing rules](MANIFEST.md#safe-markdown-writing). The source notes remain authoritative; the dashboard must never become the only place where an edit exists.

## Target for the first write release

The initial gates supported **complete/reopen one non-recurring checkbox task** and **set/remove one due date**. Subsequent increments added title wording and a guarded **single-line multi-field form**: tags, standard status, priority, Tasks emoji-format dates, restricted recurrence rules, and references to existing task IDs. The Kanban increment adds one-file card moves with child lines and one-line workflow-tag moves, both requiring review after drag-and-drop. Leave task creation, custom statuses, arbitrary grammar, cross-file moves and recurrence generation for later. Do not make the sample or real vault an automated write test fixture.

Editing starts **disabled by default**. The `--allow-writes` switch enables it for a chosen `--projects-dir`; without it, the dashboard remains entirely read-only. The calendar icon and task text open a centered editor; one **Review changes** action shows source file and line plus the exact before/after task line, followed by explicit confirmation. The source-location link remains the route to Obsidian. After success it rescans; on conflict it refuses the edit and asks for refresh, never silently retrying or overwriting.

## Write contract and identity

1. The browser identifies a task by its relative source path, **1-based line number**, exact original line, and a digest of the **entire source file as read for the current view**. This is an ephemeral edit handle, *not* a durable ID. Two identical task lines in a file are still distinct by line number.
2. On submission, the server validates that the relative path is inside the configured Projects root and not an excluded or symlinked file/directory. Do not accept an arbitrary client-supplied absolute path. Re-read the file as bytes and compare its digest, target line and task syntax to the presented snapshot. **Any intervening file change fails closed**; no best-effort relocation by task text.
3. Only a checkbox line recognized by the existing parser is editable. Treat malformed dates, ambiguous duplicate `📅` markers, malformed frontmatter/fences and unsupported task syntax as read-only. Never mutate lines in code fences, frontmatter or Obsidian Kanban settings.
4. Do not add technical IDs to existing notes for this first release. This snapshot handle is sufficient for a single-line guarded edit; introduce persistent identity only before move operations, recurrence history or synchronization.
5. A task with `🔁` is **not completable in the first write release**: doing so without generating the next occurrence would silently drop a recurring responsibility. Continue to display it read-only until recurrence semantics are designed and tested.

## Minimal transformations

- **Complete:** change only the checkbox marker `[ ]` to `[x]`. **Reopen:** change `[x]` or `[X]` to `[ ]`. Preserve indentation, list marker, text, tags, wikilinks, block IDs, completion-date markers, nested tasks and all other lines exactly. Do not silently append or remove `✅ YYYY-MM-DD` yet; make a separate decision about completion metadata before supporting it.
- **Due date:** replace exactly one valid `📅 YYYY-MM-DD` token, insert one when absent, or remove that token when explicitly cleared. Use a validated ISO date. Define and test placement that preserves a trailing Obsidian `^block-id`, tags and other metadata. Refuse ambiguous or unsupported variants rather than guessing. A due-date change does not generate or complete a recurring task.
- **Title wording (later UI increment):** replace only the wording preceding the first recognized metadata token, retaining the checkbox, tags, due/completion/recurrence markers and block ID. Reject empty wording, line breaks and newly entered metadata; if the note's syntax is ambiguous, edit it in Obsidian instead.
- **Task metadata (later UI increment):** allow multiple supported changes on one line in one confirmation, validating dates, priority, tags, supported `every ...` recurrence and comma-separated dependency IDs against the selected Projects directory. Refuse missing or duplicate IDs and cycles. Custom statuses, names-to-ID matching, cross-file *Before this* dependencies and recurrence generation remain outside this contract.
- **Kanban moves (later increment):** require a currently scanned, unmodified file snapshot and an exact lane belonging to the task's project. Ordinary-note tasks stay in place and replace only a recognized `#todo/<lane>` tag; preserve unrelated tags. For a top-level task in the paired project board, move the contiguous card and its indented child lines to a heading in that same file, preserving other bytes and settings. Ambiguous board/tag syntax and orphan boards fail closed. A drop opens a review dialog; confirmation rechecks the snapshot and writes atomically. Never silently change completion when moving to Done.
- **Combined task edits and lane changes:** the editor reviews a single prospective write of field changes and the selected lane. Ordinary-note changes remain on one line; paired-board cards can move with child lines in the same file. Creating a new lane is a different confirmation and only adds a validated `##` heading to a paired board; do not combine board creation with editing a task in another file. Refresh/reopen a board task after its board gained a lane, because its file snapshot is stale.
- Treat the original file as bytes; change only the target line's bytes. Preserve UTF-8 BOM if present, line endings (including mixed endings), trailing newline, mode and unrelated whitespace. Fail on undecodable input instead of normalizing a whole file.

## Safe replacement and limits

1. Construct the one-line replacement in memory, then parse and validate the prospective result. Ensure the expected checkbox or date change is the **only** byte difference and the target task is still the same task.
2. Immediately before writing, verify the expected file content and type again. Write a temporary file in the same directory, flush and `fsync` it, preserve required file mode, atomically `os.replace` the original, then sync the containing directory where supported. Clean up only our temporary file on failure.
3. Serialize writes within a MarkTask process with a per-file in-process lock and the content recheck; separate MarkTask processes and Obsidian do **not** promise to honor that lock. An external edit in the tiny interval after the final comparison is still a possible race—do not claim a perfect transactional guarantee. Keep edits minimal, report conflicts, and require a normal vault backup before real-data editing. Git history is useful but not a backup by itself.
4. Do not create backups, lock files, task IDs or database state *inside the vault* without an explicit design decision. Avoid full-file reformats, cross-file rewrites and writes through symlinks.

## Implementation order and gates

### Gate A — writer without dashboard controls

Extract the guarded writer into a small module independent of Dash. Add a dry-run function that returns an exact before/after preview without touching disk. Add the guarded commit function, with typed results for success, stale snapshot, unsupported task, invalid request and I/O failure. Use only synthetic temporary vaults in tests.

**Acceptance:** a valid checkbox edit changes just its marker; a repeated or stale submit changes nothing; edits outside the root, through symlinks or to excluded files fail; injected failures do not truncate the source.

### Gate B — complete/reopen UI

Add a clearly labelled action on eligible task cards and rows, with preview and confirmation. Only show active controls when `--allow-writes` is set. Recheck the snapshot server-side on click, rescan after success, and show actionable conflict feedback. Keep Obsidian links and read-only operation intact.

**Acceptance:** UI integration tests exercise success, cancellation, stale data and recurring-task refusal; no edit is possible with default CLI options.

### Gate C — due-date editing

Add a validated date input and an explicit remove-date action, reusing the writer and conflict handling. Display exactly what token will change; refuse duplicate or malformed due markers.

**Acceptance:** tests cover add/change/remove, malformed dates, CRLF/LF, a trailing block ID, Unicode, nested checkboxes and unaffected adjacent lines. Today/Upcoming/Overdue views reflect the edit after refresh.

### Gate D — cautious real-vault trial

Only after synthetic tests and a read-only scan of the **chosen** real Projects directory: confirm a separate approved backup exists, select a harmless test note, review the proposed diff, and perform one manual write with the vault owner's approval. Verify in Obsidian and compare file bytes/diff. If it fails, stop and fix the writer rather than broadening scope.

## Later, not in this editing increment

- Creating tasks, editing arbitrary unrecognized task syntax, moving across projects/files, and Kanban drag-and-drop without confirmation.
- Automatically assigning task IDs, editing *Before this* dependencies across files, custom Tasks statuses, broader recurrence grammar and the exact interaction with Obsidian Tasks/Kanban plugin-specific behavior.
- Recurring-task generation and idempotency (must be solved before recurring tasks can be completed from MarkTask).
- Stable cross-edit IDs, status history, notification state or multi-device conflict resolution.

These need their own grammar and recovery tests before enabling any corresponding button.
