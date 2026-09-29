# MarkTask

A local task index and Dash dashboard over a user-selected directory of Markdown project files. **Read-only by default**; guarded edits to existing task lines require explicit opt-in. The Markdown files remain authoritative.

## Install and run

Requires Python 3.11+ and Git. Clone the public **MarkTask code repository** (no GitHub login needed):

```sh
git clone https://github.com/Hendrik240298/marktask.git
cd marktask
```

### Python venv (no uv required)

On Linux/macOS:

```sh
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m marktask.cli scan --projects-dir /path/to/your/1-Projects
./.venv/bin/python -m marktask.cli serve --projects-dir /path/to/your/1-Projects
```

On Windows (PowerShell):

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m marktask.cli scan --projects-dir 'C:\path\to\your\1-Projects'
.\.venv\Scripts\python.exe -m marktask.cli serve --projects-dir 'C:\path\to\your\1-Projects'
```

`requirements.txt` installs this checkout in editable mode; runtime dependencies (Dash and PyYAML) are declared once in `pyproject.toml`. Run the pip command again after pulling code changes. `.venv/` is Git-ignored, and you do not need to activate it. Pip needs access to a package index or an approved local mirror/cache to obtain dependencies and the build backend. If Windows has no `py` launcher, use `python` instead of `py -3` (with Python 3.11+).

### With uv (optional)

```sh
uv sync
uv run marktask scan --projects-dir /path/to/your/1-Projects
uv run marktask serve --projects-dir /path/to/your/1-Projects
```

Open `http://127.0.0.1:8050`. Use `--port 8051` if needed. A public GitHub repository can be cloned without a GitHub login, but cloning and first-time dependency installation need network access. **No vault or example `1-Projects/` is included in the repository**: pass the direct path to a Projects directory on that machine. MarkTask never selects one automatically. The dashboard is read-only unless you explicitly pass `--allow-writes`.

The name **MarkTask** here refers to this repository and its local command. An unrelated project already uses `marktask` on PyPI; do **not** use `pip install marktask` to install this application. Both setup methods install this checkout into its own environment instead.

### Guarded editing (optional)

The default commands above cannot edit tasks. Once you have an approved backup and are ready to test on a **small synthetic or disposable** Projects directory, start with:

```sh
uv run marktask serve --projects-dir /path/to/disposable/1-Projects --allow-writes
```

Without uv, replace `uv run marktask` with `./.venv/bin/python -m marktask.cli` (or `.\.venv\Scripts\python.exe -m marktask.cli` on Windows) in any command below.

On Windows, start a **new server process** with editing enabled if you want the task-text button to open the MarkTask editor:

```powershell
.\.venv\Scripts\python.exe -m marktask.cli serve --projects-dir 'C:\path\to\your\1-Projects' --allow-writes
```

If clicking task text opens Obsidian in a normal task view, the server is running in read-only mode; `--allow-writes` is a startup option, not a dashboard toggle. The `file.md:line` **source link** always opens Obsidian, including when editing is enabled. Tasks in **Reference** also open Obsidian instead of the editor. Keep writes disabled on a real vault until you have a backup and have tested on disposable notes.

Each task gets a **calendar icon** beside its due date. Pick a date to open a review dialog. **Click the task text** to edit its wording, supported metadata and lane in that dialog. Use **Review changes** once to see the exact before/after Markdown, then **Confirm change** or cancel. Editing fields together with a lane change is one guarded write to that task's file; a native board card and its child lines can move as part of that write. The source-location link beneath the card opens Obsidian.

Supported fields: task text and space-separated tags; standard To do `[ ]`, Done `[x]`, and Cancelled `[-]` status; priority; due, scheduled, start, created, done and cancelled dates; a restricted set of recurrence rules (`every day`, `every weekday`, `every week`, `every month`, `every year`, or `every N days/weeks/months/years`, optionally `when done`); and **Depends on** as comma-separated IDs of existing, uniquely identified tasks in the selected Projects directory. The Tasks plugin's *Before this* picker, automatic task-ID assignment, custom statuses, arbitrary recurrence rules and *Only future dates* display preference are not reproduced. Recurrence rules may be edited, but recurring tasks cannot be completed or cancelled here until next-occurrence generation is implemented. Creating new tasks is not available. For ambiguous syntax or changes spanning tasks/files, edit in Obsidian instead.

The editor uses the [Obsidian Tasks emoji format](https://publish.obsidian.md/tasks/Reference/Task+Formats/Tasks+Emoji+Format) and [dependency IDs](https://publish.obsidian.md/tasks/Getting+Started/Task+Dependencies), not Tasks' full modal or natural-language date parser. It does not promise that an ID in a different vault folder is visible to this selected Projects directory.

After success the dashboard rescans; if a note changed since you opened the view, MarkTask refuses the edit and asks you to refresh. Clearing a date field removes that date's token. The Today/Upcoming/Overdue views still use **due dates**, not scheduled or start dates.

Do **not** enable writes against your real vault as the first test. The [editing plan](EDITING_PLAN.md) reserves the real-vault trial for a specific approved note after confirming a separate backup. There is no automatic vault backup, undo, or multi-process conflict guarantee. Existing task fields change one line at a time; guarded moves of native board cards can relocate their child lines within that same file. No task creation or recurring-task generation yet.

### Moving cards on a project Kanban

With `--allow-writes`, drag an open top-level card onto another lane. The drop opens a before/after preview; **nothing changes until you confirm**. Cancel, stale source content, ambiguous workflow tags, malformed card boundaries and invalid lanes fail without writing. Moves never change checkbox completion; reopen completed/cancelled tasks separately. Nested checkbox lines on a native board move with their parent, not independently.

- A task in an ordinary note stays in that note. A move replaces its one recognized workflow tag with `#todo/<lane-slug>` (`#todo` for Backlog); other tags and child lines remain untouched. For example, `Doing - Personal` uses `#todo/doing-personal`. Tags such as `#todo/privat` remain context tags unless `Privat` is an actual lane. Multiple recognized workflow tags block the move until resolved manually.
- A task in the project's paired `_Kanban*.md` file moves **with its indented child lines** under the destination `##` heading in the same file, so Obsidian Kanban sees the change. It does not gain a workflow tag. An unpaired nested board is shown as note tasks in its parent project, but its headings do not define lanes and its board cards cannot be moved in MarkTask.
- Indented checkbox tasks are subtasks of the nearest less-indented checkbox in the same note. They do not get separate Kanban cards; a parent card shows its direct subtask count. An open subtask with its own due date still appears independently in Today, Upcoming and Overdue. Indented non-checkbox bullets appear as read-only notes in that task's detail dialog. A subtask's own fields can be edited after review, but its lane is inherited with its parent rather than moved separately.
- A project's `_Kanban*.md` beside its master note defines its own lanes, even empty ones. Nested folders with their own master notes form separate projects. Without a paired board, the existing standard lanes are available to tagged ordinary-note tasks. Legacy `#inbox`, `#waiting`, `#doing` and `#next` tags remain readable; bare `#todo` means Backlog.

The task editor's **Lane** field can be changed along with task wording, priority or dates in a single before/after review. For projects with a paired board, expand **+ New lane** to name a lane, then separately review and confirm insertion of its `##` heading in that board file. It does **not** move the task automatically. After creating a lane, select it for the task; if the edited task lives in the board note itself, reopen the task first because the new heading changed its file snapshot. Lane creation is unavailable without a paired board. The edit and create operations are separate confirmations, never a two-file transaction.

The dashboard is the aggregation view; moving a task in an ordinary note does **not** copy it into an Obsidian board file. Drag-and-drop uses a small browser asset and still requires an interactive browser check before treating it as real-vault verified.

On a project Kanban, **Order cards by** switches between Due date (the default) and Priority. Priority follows Obsidian Tasks' highest/high/medium/normal/low/lowest markers, highest first; ties use due date, then source location. This is display-only and does not reorder Markdown. Workspace tables default to due-date ordering, with their own column-header controls.

Workspace tables (Inbox, Today, Upcoming, Overdue, Waiting, All tasks and Reference) show **Priority** and have clickable headers for Status, Task, Project, Column, Due, Priority and Source. Click a header again to reverse its direction. Due date starts earliest first; Priority starts highest first when selected; undated tasks remain last even when reversing Due. Sorting happens before the 150-row display limit and changes only the current browser view, never Markdown. The selected order carries across workspace views until you reload the page; Kanban's separate sort switch is unaffected.

### Opening tasks in Obsidian

Click a task's **source location** to open its note in Obsidian. In read-only mode, its text also opens Obsidian; with `--allow-writes`, clicking the text opens MarkTask's editor instead. The editor's `file.md:line` reference is also a clickable Obsidian link. The browser may ask for permission to launch the `obsidian://` protocol. The displayed location remains copyable.

- By default, core Obsidian opens the **file** using its absolute path. If the checkbox line already ends in an Obsidian `^block-id` and MarkTask can locate the vault's `.obsidian` directory, the link jumps to that block instead. Obsidian's core URI does **not** document jumping to arbitrary line numbers, and MarkTask never inserts block IDs into your notes.
- For **exact line** navigation on every task, install and enable the optional [Advanced URI Obsidian plugin](https://github.com/Vinzent03/obsidian-advanced-uri), then launch MarkTask with `--advanced-uri`:

  ```sh
  uv run marktask serve --projects-dir /path/to/real/1-Projects --advanced-uri
  ```

  MarkTask finds the containing vault by its `.obsidian` folder. If your vault uses a custom configuration folder or cannot be detected, also pass `--obsidian-vault-root /path/to/vault`. If the vault name differs from its folder name, pass `--obsidian-vault 'Vault Name'` (the vault ID also works). The plugin's line numbers are 1-indexed and refer to the **last scan**; use Refresh files after editing a note. This option changes only links, never Markdown.

Core file links work with just `--projects-dir`, provided Obsidian knows the vault containing that path. Sample notes open only if their directory belongs to a registered vault. On Linux, Obsidian must be registered as the `obsidian://` URL handler.

Alternatively install with `python -m pip install -e '.[dev]'` and use `marktask` in that environment. The path is required; MarkTask does not silently fall back to the sample. `scan` prints counts and file/line warnings, not task text. Use repeatable `--exclude NAME` to skip directories or files with that name anywhere below the Projects directory. Default scanner exclusions: `.git`, `.obsidian`, `attachments`, `generated`. Symlinked directories and files are not followed.

### Reference visibility

Go to **Reference** in the sidebar: **Manage visibility** opens there automatically. It is also available as a collapsed panel on **Overview**. With `--allow-writes`, choose **Files & folders** or **Tasks**, then **Hide matches** or **Remove a rule**. For files/folders, paste an absolute path under the selected Projects directory, drop **path text** in the drop zone, or enter a filename/folder name or relative path glob (for example `Work/archive/*`). Browsers may not reveal the absolute path of a native file-manager drag; if the drop zone says so, paste the path instead. An absolute path is validated against the selected Projects directory and stored as a root-anchored relative rule (`./Work/archive/*` for a folder), never as a machine-specific absolute path. For tasks, enter a text fragment, optionally scoped to a file (`Work/tasks.md :: task text`). Click **Review rule**, inspect every affected file and task, then **Confirm rule**. Hidden items remain scanned and appear in Reference; they do not appear in Kanban, All tasks, date views, actionable counts or searches in those views. Reference tasks open in Obsidian instead of the task editor. File names match any filename/folder component; task text matches case-insensitively, with optional glob wildcards. Matching task text can hide more than one task, so inspect the preview before confirming. Regex is not supported.

The file and task rules live in `.marktask-visibility.json` at the selected Projects directory's top level, **not** in a Markdown note. Without a rules file, the `templates` folder name is hidden by default but available in Reference; remove that rule if desired. No file is created until a rule is confirmed, and read-only mode never changes it. To keep the configuration outside the Projects directory instead, pass an explicit `--visibility-file /path/to/rules.json` (the parent directory must already exist). Invalid config blocks the dashboard rather than unexpectedly showing hidden tasks. Unlike `--exclude`, these rules only affect visibility; `--exclude` still removes files from scanning and the Reference view entirely.

## Current behavior

- Direct child folders are projects; a nested folder with its own unambiguous `_ProjectName.md` master note becomes a separate project, and other nested folders belong to their nearest ancestor project. Loose Markdown files belong to `(root)`.
- Standard Markdown checkbox lines (`- [ ]`, `- [x]`, `- [X]`, `- [-]`, and indented checkboxes) in **any** scanned note are tasks; optional `📅 YYYY-MM-DD` due dates, `🔁` recurrence text, and `#tags` are indexed. Recurrence is displayed only; no tasks are generated. Malformed due dates create warnings.
- The sidebar has Inbox, Today, Upcoming, Overdue, Waiting, All tasks, Reference and a live list of projects. Click a project in the sidebar, a task table's Project column, or on the overview to open its Kanban of tasks from its own notes and board; guarded drag-and-drop moves are available only with `--allow-writes`.
- The selected project's view starts with a **collapsed** `_ProjectName.md` master-note panel above the Kanban. Only Overview shows the workspace-wide metrics. Expand the note panel to see YAML properties and a Markdown preview; its source link opens Obsidian. If the filename differs from the folder name, MarkTask uses the only other `_*.md` file in that folder (excluding `_Kanban*.md`); if there are several, it does not guess. Missing, unreadable, or ambiguous notes show a message. The preview updates when you refresh the view and never writes to the master note. Simple Obsidian callouts display as blockquotes; `[[wikilinks]]` to uniquely identified notes in the selected Projects tree open the actual file in Obsidian. Unresolved/ambiguous links show as plain names rather than guessing, and links outside the selected Projects tree cannot be resolved. Heading targets currently open the file, not the specific heading. Embedded images are shown as text rather than fetched.
- Inbox contains **incomplete** tasks explicitly tagged `#inbox` (including namespaced tags like `#inbox/privat`) or placed in a native Obsidian Kanban `Inbox` column; it does not automatically scoop up every task without a status.
- Completed checkboxes go to Done. On the paired project board, native `##` headings take precedence and keep their original names. For ordinary notes, `#todo/<lane-slug>` selects a matching lane; bare `#todo` and unmatched tags go to Backlog. The prior `#inbox`, `#waiting`, `#blocked`, `#doing`, `#in-progress` and `#next` tags still map to their matching standard lanes when no explicit workflow tag overrides them. Read-only scans do not change your files.
- Today and Overdue are mutually exclusive; Upcoming is tomorrow through seven calendar days from today, inclusive. All time comparisons use the machine's local date.
- The dashboard includes project cards, a per-project Kanban, date and waiting views, search within the current view by task/source path, clickable project names in task tables, Obsidian links, copyable source file and line, and manual refresh. It limits table rows to 150 per view; narrow the search to see more. The clipboard location is relative to the selected Projects directory.
- The interface ships with its own Todoist-inspired **dark** charcoal/red palette; it does not need a browser dark-mode extension. No Todoist assets or code are used.
- File permissions and UTF-8 errors are reported without aborting a scan. No persistent database, telemetry, external requests, automatic reminders, or file watchers. The server binds to `127.0.0.1` only; opt-in editing is **not authenticated** and should not be exposed beyond localhost.

## Development

```sh
uv run --extra dev pytest
```

With a standard venv, install test dependencies and run the tests:

```sh
./.venv/bin/python -m pip install -e '.[dev]'
./.venv/bin/python -m pytest
```

The synthetic editing tests do not touch the bundled `1-Projects/` sample. That sample is ignored by Git and should not be committed without checking provenance and sensitivity. See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the roadmap, [EDITING_PLAN.md](EDITING_PLAN.md) for write-safety limits and the pending real-vault trial, and [MANIFEST.md](MANIFEST.md) for the larger vision.

## License

MarkTask is available under the [MIT License](LICENSE).
