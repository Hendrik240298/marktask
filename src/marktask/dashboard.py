"""Local dashboard with explicitly opt-in, guarded single-task editing."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import date
import json
from pathlib import Path
from urllib.parse import parse_qs, urlencode

from dash import ALL, Dash, Input, Output, State, ctx, dcc, html, no_update

from marktask.index import DUE, Index, Task, priority_rank, scan, task_column, visible_tasks
from marktask.links import ObsidianLinks, find_vault_root
from marktask.project_note import WIKILINK, load_project_note, preview_markdown
from marktask.visibility import (VisibilityError, VisibilityRules, is_reference, is_reference_task,
                                 file_rule_from_input, load_rules, save_rules, validate_task_pattern)
from marktask.writer import EditError, EditHandle, InvalidEdit, StaleSnapshot, TaskWriter, UncertainWrite


VIEWS = ("projects", "kanban", "inbox", "today", "overdue", "upcoming", "waiting", "all", "reference")
BOARD_ORDER = ("Inbox", "Backlog", "To Do", "Next", "In Progress", "Waiting", "Review", "Done")
BOARD_PAGE_SIZE = 12
TABLE_COLUMNS = (("status", "Status"), ("task", "Task"), ("project", "Project"),
                 ("column", "Column"), ("due", "Due"), ("priority", "Priority"),
                 ("source", "Source · line"))
DEFAULT_TABLE_SORT = {"column": "due", "direction": "asc"}
PRIORITY_LABELS = {"lowest": "Lowest ⏬", "low": "Low 🔽", "normal": "Normal",
                   "medium": "Medium 🔼", "high": "High ⏫", "highest": "Highest 🔺"}


def route(search: str | None) -> tuple[str, str | None]:
    params = parse_qs((search or "").lstrip("?"))
    view = params.get("view", ["projects"])[0]
    if view == "kanban" and params.get("project"):
        return "kanban", params["project"][0]
    if view in VIEWS and view != "kanban":
        return view, None
    return "projects", None


def sidebar(index: Index, view: str, project: str | None, today: date, allow_writes: bool = False) -> list:
    def link(label: str, target: str, icon: str, count: int | None = None, active: bool = False):
        return dcc.Link([
            html.Span(icon, className="nav-icon", **{"aria-hidden": "true"}),
            html.Span(label, className="nav-label"),
            html.Span(str(count), className="nav-count") if count is not None else None,
        ], href=target, className="nav-link" + (" active" if active else ""))

    items = [
        ("Inbox", "inbox", "▤"), ("Today", "today", "☀"),
        ("Upcoming", "upcoming", "▦"), ("Overdue", "overdue", "!"),
        ("Waiting", "waiting", "◷"),
    ]
    return [
        html.Div([html.Span("◈", className="brand-icon"), html.Span("MarkTask")], className="brand"),
        html.Nav([
            *[link(label, "/?" + urlencode({"view": name}), icon,
                   len(visible_tasks(index.tasks, name, today)), view == name)
              for label, name, icon in items],
            link("All tasks", "/?view=all", "≡", active=view == "all"),
            link("Reference", "/?view=reference", "◇", active=view == "reference"),
        ], className="side-nav", **{"aria-label": "Task views"}),
        html.Div([
            html.P("PROJECTS", className="side-heading"),
            link("All projects", "/", "▦", active=view == "projects"),
            html.Nav([
                link(name, "/?" + urlencode({"view": "kanban", "project": name}), "•",
                      sum(not task.completed and not task.cancelled and task.project == name for task in index.tasks),
                     view == "kanban" and project == name)
                for name in index.projects
            ], className="side-nav project-nav", **{"aria-label": "Projects"}),
        ], className="side-projects"),
        html.Div("LOCAL · GUARDED EDITING" if allow_writes else "LOCAL · READ ONLY", className="side-footer"),
    ]


def summary(index: Index, today: date) -> list:
    counts = [
        ("Projects", len(index.projects)),
        ("Open", sum(not task.completed and not task.cancelled for task in index.tasks)),
        ("Today", len(visible_tasks(index.tasks, "today", today))),
        ("Overdue", len(visible_tasks(index.tasks, "overdue", today))),
        ("Waiting", len(visible_tasks(index.tasks, "waiting", today))),
    ]
    return [html.Div([html.Span(label), html.Strong(str(value))], className="metric") for label, value in counts]


def project_cards(index: Index, tasks: list[Task]) -> list:
    cards = []
    for project in index.projects:
        grouped = [task for task in tasks if task.project == project]
        open_count = sum(not task.completed and not task.cancelled for task in grouped)
        next_due = min((task.due for task in grouped if not task.completed and not task.cancelled
                        and task.due is not None), default=None)
        cards.append(dcc.Link(html.Div([
            html.H3(project),
            html.P(f"{open_count} open · {len(grouped)} total"),
            html.Small(f"Next due: {next_due.isoformat() if next_due else '—'}"),
        ], className="project-card"), href="/?" + urlencode({"view": "kanban", "project": project}),
            className="project-link"))
    return cards


def task_link(text: str, task: Task, links: ObsidianLinks, class_name: str) -> html.A:
    uri, title = links.for_task(task)
    return html.A(text, href=uri, target="_blank", rel="noopener noreferrer",
                  title=title, className=class_name)


def note_links(text: str, source: str, links: ObsidianLinks, sources: tuple[str, ...]) -> list:
    """Render wikilinks as Obsidian anchors only for unambiguous indexed files."""
    result: list = []
    start = 0
    for match in WIKILINK.finditer(text):
        result.append(text[start:match.start()])
        target, separator, alias = match.group(1).partition("|")
        label = alias if separator else target.split("#", 1)[0] or target
        uri = links.for_wikilink(target.strip(), source, sources)
        result.append(html.A(label, href=uri, target="_blank", rel="noopener noreferrer",
                             className="wikilink") if uri else
                      html.Span(label, className="unresolved-wikilink",
                                title="Not uniquely found in Projects"))
        start = match.end()
    result.append(text[start:])
    return result


def project_note_panel(projects_dir: Path, project: str, links: ObsidianLinks,
                       sources: tuple[str, ...] = ()) -> html.Section:
    note = load_project_note(projects_dir, project)
    heading = [html.Summary("Project note", className="project-note-toggle")]
    content = []
    if note.source:
        content.append(html.A("Open in Obsidian ↗", href=links.for_note(note.source), target="_blank",
                              rel="noopener noreferrer", className="project-note-link"))
        content.append(html.Small(note.source, className="project-note-source"))
    if note.message:
        content.append(html.P(note.message, className="hint"))
    if note.properties:
        content.append(html.Div([
            html.Div([html.Dt(key), html.Dd(note_links(value, note.source or "", links, sources))],
                     className="project-property")
            for key, value in note.properties
        ], className="project-properties"))
    if note.raw_properties is not None:
        content.append(html.Pre(note.raw_properties, className="project-note-raw"))
    if note.body.strip():
        content.append(dcc.Markdown(preview_markdown(
            note.body, lambda target: links.for_wikilink(target, note.source or "", sources)),
            className="project-note-body", dangerously_allow_html=True))
    return html.Section(html.Details([*heading, html.Div(content, className="project-note-content")]),
                        className="project-note", **{"aria-label": "Project master note"})


def edit_key(task: Task) -> str:
    return json.dumps(EditHandle.from_task(task).as_dict(), ensure_ascii=False)


def task_text(task: Task, links: ObsidianLinks, allow_writes: bool,
              sources: tuple[str, ...] = ()):
    main = (html.Button(task.text, id={"type": "edit-task", "key": edit_key(task)},
                        n_clicks=0, className="task-link task-edit-trigger",
                        title="Edit task in MarkTask; use the source link to open Obsidian",
                        **{"aria-label": f"Edit task: {task.text}"}) if allow_writes else
            task_link(task.text, task, links, "task-link"))
    if not sources:
        return main
    related = [link for link in note_links(task.text, task.source, links, sources) if isinstance(link, html.A)]
    return html.Span([main, html.Span([" · ", *related], className="related-note-links")]) if related else main


def task_detail_context(task: Task, tasks: tuple[Task, ...], links: ObsidianLinks,
                        sources: tuple[str, ...] = ()) -> list:
    """Read-only context for one task; edits still go through the guarded line writer."""
    children = [child for child in tasks if child.source == task.source and child.parent_line == task.line]
    result = []
    if task.parent_line is not None:
        parent = next((item for item in tasks if item.source == task.source and item.line == task.parent_line), None)
        if parent:
            result.append(html.P(["Subtask of ", *note_links(parent.text, parent.source, links, sources), " · ",
                                  task_link(f"line {parent.line}", parent, links, "source-link")],
                                 className="task-parent"))
    if task.notes:
        result.append(html.Section([html.H3("Notes"), html.Ul([
            html.Li(note_links(note, task.source, links, sources)) for note in task.notes])],
                                   className="task-context-section"))
    if children:
        result.append(html.Section([html.H3(f"Subtasks · {len(children)}"), html.Ul([
            html.Li([html.Span("✓ " if child.completed else "− " if child.cancelled else "○ "),
                     *note_links(child.text, child.source, links, sources), " · ",
                     task_link(f"line {child.line}", child, links, "source-link")])
            for child in children
        ])], className="task-context-section"))
    if not result:
        result.append(html.P("No notes or subtasks in this note.", className="hint"))
    return result


def due_picker(task: Task) -> html.Label:
    return html.Label([
        html.Span("📅", **{"aria-hidden": "true"}),
        html.Span(f"Choose due date for {task.text}", className="sr-only"),
        dcc.Input(id={"type": "quick-due", "key": edit_key(task)}, type="date",
                  value=task.due.isoformat() if task.due else None,
                  className="quick-due-input"),
    ], className="quick-due", title="Choose a due date")


FORM_FIELDS = ("title", "due", "scheduled", "start", "created", "done", "cancelled",
               "priority", "recurrence", "tags", "depends_on", "status")


def form_id(name: str) -> str:
    return "edit-status-choice" if name == "status" else f"edit-{name}"


def edit_form() -> list:
    def text_field(name: str, label: str, hint: str = "") -> list:
        return [html.Label(label, htmlFor=f"edit-{name}"),
                dcc.Input(id=f"edit-{name}", type="text", placeholder=hint)]

    def date_field(name: str, label: str) -> list:
        return [html.Label(label, htmlFor=f"edit-{name}"), dcc.Input(id=f"edit-{name}", type="date")]

    return [
        *text_field("title", "Task text"),
        html.Label("Status", htmlFor="edit-status-choice"),
        dcc.Dropdown(options=[{"label": label, "value": value} for value, label in
                              (("todo", "To do [ ]"), ("done", "Done [x]"), ("cancelled", "Cancelled [-]"))],
                     id="edit-status-choice", value="todo", clearable=False, searchable=False,
                     className="edit-dropdown"),
        html.Label("Priority", htmlFor="edit-priority"),
        dcc.Dropdown(options=[{"label": label, "value": value} for value, label in
                              (("normal", "Normal"), ("lowest", "Lowest ⏬"), ("low", "Low 🔽"),
                               ("medium", "Medium 🔼"), ("high", "High ⏫"), ("highest", "Highest 🔺"))],
                     id="edit-priority", value="normal", clearable=False, searchable=False,
                     className="edit-dropdown"),
        html.Label("Lane", htmlFor="edit-lane"),
        dcc.Dropdown(id="edit-lane", clearable=False, searchable=False, className="edit-dropdown"),
        html.Details([
            html.Summary("+ New lane"),
            html.Div([
                dcc.Input(id="new-lane-name", type="text", placeholder="Name this lane", maxLength=64),
                html.Button("Review new lane", id="preview-lane", n_clicks=0),
            ], className="new-lane-row"),
        ], id="new-lane-controls", className="new-lane-controls", style={"display": "none"}),
        *date_field("due", "Due"),
        *text_field("tags", "Tags", "#work #next"),
        html.Details([
            html.Summary("More Tasks fields"),
            html.Div([
                *date_field("scheduled", "Scheduled"), *date_field("start", "Start"),
                *date_field("created", "Created"), *date_field("done", "Done date"),
                *date_field("cancelled", "Cancelled date"),
                *text_field("recurrence", "Recurs", "e.g. every week when done"),
                *text_field("depends_on", "Depends on task IDs", "e.g. task_1,other-id"),
                html.P("Dependencies use existing IDs (⛔). 'Before this' and automatic ID assignment "
                       "require changes to other tasks and are not supported. 'Only future dates' is "
                       "a Tasks-plugin display preference, not task metadata.", className="hint"),
            ], className="edit-advanced-fields"),
        ], className="edit-advanced"),
        html.P("Clear a date field to remove its token. Review the Markdown line before confirming.", className="hint"),
    ]


def kanban_board(tasks: list[Task], links: ObsidianLinks, allow_writes: bool = False,
                  lanes: tuple[str, ...] = (), sort_by: str = "due",
                  all_tasks: tuple[Task, ...] = (), sources: tuple[str, ...] = (),
                  max_per_lane: int | None = BOARD_PAGE_SIZE) -> list:
    grouped: dict[str, list[Task]] = {name: [] for name in lanes}
    for task in tasks:
        if task.parent_line is not None:
            continue
        grouped.setdefault(task_column(task), []).append(task)
    if not grouped:
        return [html.P("No tasks in this project yet.", className="empty")]

    def order(column: str) -> tuple[int, str]:
        canonical = next((i for i, name in enumerate(BOARD_ORDER) if name.casefold() == column.casefold()), None)
        if column.casefold() == "done":
            return (len(BOARD_ORDER), column.casefold())
        return (canonical if canonical is not None else len(BOARD_ORDER) - 1, column.casefold())

    columns = []
    remaining = 0
    child_counts = Counter((task.source, task.parent_line) for task in all_tasks
                           if task.parent_line is not None)
    names = [*lanes, *(name for name in sorted(grouped, key=order) if name not in lanes)]
    for name in names:
        cards = []
        ordered = (sorted(grouped[name], key=lambda task: (-priority_rank(task), task.due or date.max,
                                                           task.source, task.line))
                   if sort_by == "priority" else grouped[name])
        visible = ordered[:max_per_lane] if max_per_lane is not None else ordered
        remaining += len(ordered) - len(visible)
        for task in visible:
            location = f"{task.source}:{task.line}"
            movable = (allow_writes and not task.completed and not task.cancelled
                       and (not task.is_board or task.board_source == task.source and not task.original[0].isspace()))
            targets = task.lanes if task.is_board else tuple(dict.fromkeys(("Backlog", *task.lanes)))
            child_count = child_counts[(task.source, task.line)]
            cards.append(html.Article([
                html.Div(task_text(task, links, allow_writes, sources), className="card-text"),
                html.Span(f"{child_count} subtask{'s' if child_count != 1 else ''}", className="subtask-count")
                if child_count else None,
                html.Div([
                    html.Span([due_picker(task) if allow_writes else None,
                               task.due.isoformat() if task.due else "No due date" if allow_writes else ""],
                              className="card-due"),
                    html.Span([task_link(location, task, links, "source-link"),
                               dcc.Clipboard(content=location, title="Copy source location")],
                              className="card-source"),
                ], className="card-meta"),
            ], className="task-card" + (" cancelled" if task.cancelled else " completed" if task.completed else "")
               + (" movable" if movable else ""), draggable=bool(movable),
               title="Drag to another lane to review a move" if movable else None,
               **({"data-move-key": edit_key(task), "data-move-source": name,
                   "data-move-targets": json.dumps(targets)} if movable else {})))
        columns.append(html.Section([
            html.H3([name, html.Span(str(len(ordered)), className="column-count")]),
            *cards,
        ], className="kanban-column", **({"data-move-lane": name} if allow_writes else {})))
    result = [html.Div(columns, className="kanban-board")]
    if remaining:
        result.append(html.Div([
            html.Span(f"Showing the first {max_per_lane} cards per lane · {remaining} more available"),
            html.Button(f"Show {BOARD_PAGE_SIZE} more per lane", id={"type": "board-page", "action": "more"},
                        n_clicks=0),
            html.Button("Show all cards", id={"type": "board-page", "action": "all"}, n_clicks=0),
        ], className="board-paging"))
    return result


def table_sort_choice(value: dict | None) -> tuple[str, str]:
    if (isinstance(value, dict) and isinstance(value.get("column"), str)
            and value["column"] in dict(TABLE_COLUMNS) and value.get("direction") in ("asc", "desc")):
        return value["column"], value["direction"]
    return "due", "asc"


def ordered_table_tasks(tasks: list[Task], sort_choice: dict | None) -> list[Task]:
    """Stable display-only sorting with undated tasks last in either direction."""
    column, direction = table_sort_choice(sort_choice)
    baseline = sorted(tasks, key=lambda task: (task.due or date.max, task.project.casefold(),
                                               task.source.casefold(), task.line))
    if column == "due":
        dated = [task for task in baseline if task.due is not None]
        undated = [task for task in baseline if task.due is None]
        return sorted(dated, key=lambda task: task.due, reverse=direction == "desc") + undated

    def key(task: Task):
        if column == "status":
            return 2 if task.cancelled else 1 if task.completed else 0
        if column == "task":
            return task.text.casefold()
        if column == "project":
            return task.project.casefold()
        if column == "column":
            return task_column(task).casefold()
        if column == "priority":
            return priority_rank(task)
        return task.source.casefold(), task.line

    return sorted(baseline, key=key, reverse=direction == "desc")


def task_table(tasks: list[Task], links: ObsidianLinks, allow_writes: bool = False,
               sources: tuple[str, ...] = (), sort_choice: dict | None = None) -> list:
    if not tasks:
        return [html.P("No matching tasks.", className="empty")]
    column, direction = table_sort_choice(sort_choice)
    rows = []
    for task in ordered_table_tasks(tasks, sort_choice)[:150]:
        location = f"{task.source}:{task.line}"
        rows.append(html.Tr([
            html.Td("−" if task.cancelled else "✓" if task.completed else "○", className="check"),
            html.Td([html.Span("↳ ", className="subtask-indicator", title="Subtask")
                     if task.parent_line is not None else None,
                     task_text(task, links, allow_writes, sources)], className="task-text"),
            html.Td(dcc.Link(task.project, href="/?" + urlencode({"view": "kanban", "project": task.project}),
                             className="table-project-link")),
            html.Td(task_column(task)),
            html.Td([due_picker(task) if allow_writes else None,
                     task.due.isoformat() if task.due else "—"]),
            html.Td(PRIORITY_LABELS[task.priority], className="task-priority"),
            html.Td([task_link(location, task, links, "source-link"),
                     dcc.Clipboard(content=location, title="Copy source location")], className="source"),
        ]))
    result = [html.Div(html.Table([
        html.Thead(html.Tr([html.Th(html.Button([
            label, html.Span(" ▲" if direction == "asc" else " ▼", className="sort-arrow")
            if name == column else None,
        ], id={"type": "table-sort", "column": name}, n_clicks=0, className="table-sort-button",
            title=f"Sort by {label}", **{"aria-label": f"Sort by {label}"}),
            **{"aria-sort": ("ascending" if direction == "asc" else "descending")
               if name == column else "none"}) for name, label in TABLE_COLUMNS])),
        html.Tbody(rows),
    ]), className="table-wrap")]
    if len(tasks) > 150:
        result.append(html.P(f"Showing first 150 of {len(tasks)} matches. Narrow the project or search.", className="hint"))
    return result


def visibility_panel(allow_writes: bool) -> html.Details:
    return html.Details([
        html.Summary(id="visibility-heading"),
        html.P("Hide notes, folders or task text from actionable views. They remain in Reference; "
               "no Markdown is changed.", className="hint"),
        html.P(id="visibility-rules", className="visibility-rules"),
        html.P("Files: paste/drop an absolute path inside Projects, or enter a name or relative glob. "
               "Tasks: text fragment or Work/tasks.md :: text fragment. Review every match before saving.",
               className="hint"),
        html.Div([
            dcc.Dropdown(id="visibility-kind", options=[{"label": "Files & folders", "value": "file"},
                                                    {"label": "Tasks", "value": "task"}],
                         value="file", clearable=False, searchable=False, className="edit-dropdown"),
            dcc.Dropdown(id="visibility-action", options=[{"label": "Hide matches", "value": "add"},
                                                      {"label": "Remove a rule", "value": "remove"}],
                         value="add", clearable=False, searchable=False, className="edit-dropdown"),
            html.Div([
                html.Label("Drop path text here, or paste it below", htmlFor="visibility-pattern"),
                dcc.Input(id="visibility-pattern", type="text", maxLength=1024,
                          placeholder="Absolute file/folder path, glob or task text"),
                html.Small(id="visibility-drop-feedback", className="hint"),
            ], id="visibility-drop", className="visibility-drop"),
            html.Button("Review rule", id="preview-visibility", n_clicks=0),
        ], className="visibility-controls") if allow_writes else None,
    ], id="visibility-panel", className="visibility-panel", style={"display": "none"})


def changed_visibility(index: Index, before: VisibilityRules, after: VisibilityRules) -> dict[str, list[str]]:
    return {
        "files": [source for source in index.sources if is_reference(source, before.reference_globs)
                  != is_reference(source, after.reference_globs)],
        "tasks": [f"{task.source}:{task.line} · {task.text}" for task in index.tasks
                  if is_reference_task(task, before) != is_reference_task(task, after)],
    }


def create_app(projects_dir: Path, excludes: tuple[str, ...] = (), links: ObsidianLinks | None = None,
               allow_writes: bool = False, visibility_file: Path | None = None) -> Dash:
    links = links or ObsidianLinks(projects_dir, find_vault_root(projects_dir))
    visibility_file = visibility_file if visibility_file is not None else projects_dir / ".marktask-visibility.json"
    writer = TaskWriter(projects_dir, excludes) if allow_writes else None
    app = Dash(__name__, title="MarkTask")
    fields = edit_form() if allow_writes else []
    app.layout = html.Main([
        dcc.Location(id="url", refresh=False),
        dcc.Store(id="edit-revision", data=0),
        dcc.Store(id="table-sort", data=DEFAULT_TABLE_SORT),
        dcc.Store(id="board-limit"),
        *([dcc.Store(id="edit-selected"), dcc.Store(id="edit-proposal"),
           dcc.Store(id="move-request"), dcc.Store(id="move-proposal"),
           dcc.Store(id="move-revision", data=0), dcc.Store(id="lane-proposal"),
            dcc.Store(id="lane-revision", data=0), dcc.Store(id="visibility-proposal"),
            dcc.Store(id="visibility-revision", data=0)] if allow_writes else []),
        html.Aside(id="sidebar", className="sidebar"),
        html.Div([
            html.Header([
                html.H1("Overview", id="page-title"),
                html.Button("Refresh files", id="refresh", n_clicks=0, className="refresh"),
            ], className="header"),
            html.Div(id="summary", className="metrics"),
            html.Div(id="edit-status", className="edit-status", role="status") if allow_writes else None,
            html.Div(id="move-status", className="edit-status", role="status") if allow_writes else None,
            html.Div(id="lane-status", className="edit-status", role="status") if allow_writes else None,
            html.Div(id="visibility-status", className="edit-status", role="status") if allow_writes else None,
            html.Section(html.Div([
                html.H2("Edit task"),
                html.P(id="edit-selection", className="edit-selection"),
                html.Div([
                    html.Div([
                        html.Div(fields[:2], className="edit-controls edit-title"),
                        html.Div(id="edit-task-context", className="task-context"),
                    ], className="edit-task-main"),
                    html.Div(fields[2:], className="edit-controls edit-task-fields"),
                ], className="edit-task-layout"),
                html.Pre(id="edit-diff", className="edit-diff"),
                html.Div([
                    html.Button("Review changes", id="review-edit", n_clicks=0),
                    html.Button("Confirm change", id="confirm-edit", n_clicks=0, disabled=True, className="confirm-edit"),
                    html.Button("Cancel", id="cancel-edit", n_clicks=0),
                ], className="edit-actions"),
            ], className="edit-dialog"), id="edit-panel", className="edit-panel", style={"display": "none"},
            role="dialog", **{"aria-modal": "true", "aria-label": "Review task edit"}) if allow_writes else None,
            html.Section(html.Div([
                html.H2("Move task"),
                html.P(id="move-selection", className="edit-selection"),
                html.Pre(id="move-diff", className="edit-diff"),
                html.Div([
                    html.Button("Confirm move", id="confirm-move", n_clicks=0, className="confirm-edit"),
                    html.Button("Cancel", id="cancel-move", n_clicks=0),
                ], className="edit-actions"),
            ], className="edit-dialog"), id="move-panel", className="edit-panel", style={"display": "none"},
            role="dialog", **{"aria-modal": "true", "aria-label": "Review Kanban move"}) if allow_writes else None,
            html.Section(html.Div([
                html.H2("Create Kanban lane"),
                html.P(id="lane-selection", className="edit-selection"),
                html.Pre(id="lane-diff", className="edit-diff"),
                html.Div([
                    html.Button("Confirm new lane", id="confirm-lane", n_clicks=0, className="confirm-edit"),
                    html.Button("Cancel", id="cancel-lane", n_clicks=0),
                ], className="edit-actions"),
            ], className="edit-dialog"), id="lane-panel", className="edit-panel", style={"display": "none"},
            role="dialog", **{"aria-modal": "true", "aria-label": "Review new Kanban lane"}) if allow_writes else None,
            html.Section(html.Div([
                html.H2("Review reference rule"),
                html.Pre(id="visibility-diff", className="edit-diff"),
                html.Div([
                    html.Button("Confirm rule", id="confirm-visibility", n_clicks=0, className="confirm-edit"),
                    html.Button("Cancel", id="cancel-visibility", n_clicks=0),
                ], className="edit-actions"),
            ], className="edit-dialog"), id="visibility-dialog", className="edit-panel", style={"display": "none"},
            role="dialog", **{"aria-modal": "true", "aria-label": "Review reference rule"}) if allow_writes else None,
            visibility_panel(allow_writes),
            html.Div([
                html.Label("Search this view", htmlFor="query"),
                dcc.Input(id="query", type="search", placeholder="Search task text or source path…", debounce=True),
            ], className="search-bar"),
            html.Div([
                html.Span("Order cards by", className="board-sort-label"),
                dcc.RadioItems(id="board-sort", value="due", inline=True, className="board-sort-switch",
                               options=[{"label": "Due date", "value": "due"},
                                        {"label": "Priority", "value": "priority"}]),
            ], id="board-sort-control", className="board-sort-control", style={"display": "none"}),
            html.Section([html.Div(id="results"), html.Div(id="diagnostics", className="diagnostics")], className="results"),
            html.Footer(("Guarded editing enabled" if allow_writes else "Read-only")
                        + " · Today uses your machine's local date · Upcoming = tomorrow through seven days out"),
        ], className="main-content"),
    ], className="container")

    @app.callback(
        Output("sidebar", "children"), Output("page-title", "children"), Output("summary", "children"),
        Output("results", "children"), Output("diagnostics", "children"),
        Output("visibility-panel", "style"), Output("visibility-heading", "children"),
        Output("visibility-rules", "children"),
        Input("refresh", "n_clicks"), Input("url", "search"), Input("query", "value"),
        Input("board-sort", "value"), Input("table-sort", "data"), Input("board-limit", "data"),
        Input("edit-revision", "data"),
        *([Input("move-revision", "data"), Input("lane-revision", "data"),
           Input("visibility-revision", "data")] if allow_writes else []),
    )
    def render(_clicks: int, search: str | None, query: str | None, sort_by: str | None,
               table_sort: dict | None, board_limit: dict | None, _revision: int, *_move_revision):
        try:
            index = scan(projects_dir, excludes)
        except ValueError:
            return [], "Unavailable", [], html.P("Projects directory is no longer available."), [], {"display": "none"}, "", ""
        try:
            rules, _digest = load_rules(visibility_file)
        except VisibilityError as exc:
            return [], "Unavailable", [], html.P(f"Visibility configuration error: {exc}"), [], {"display": "none"}, "", ""
        view, project = route(search)
        title = project if view == "kanban" else ("Overview" if view == "projects" else "All tasks" if view == "all" else view.title())
        today = date.today()
        hidden = tuple(source for source in index.sources if is_reference(source, rules.reference_globs))
        hidden_tasks = tuple(task for task in index.tasks if is_reference_task(task, rules))
        active = replace(index, tasks=tuple(task for task in index.tasks if not is_reference_task(task, rules)))
        selected = (visible_tasks(hidden_tasks, "all", today)
                    if view == "reference" else visible_tasks(active.tasks, view, today))
        if project:
            selected = [task for task in selected if task.project == project]
        if view == "kanban":
            selected = [task for task in selected if task.parent_line is None]
        if query:
            term = query.casefold().strip()
            selected = [task for task in selected if term in task.text.casefold() or term in task.source.casefold()]
        if view == "projects":
            listing = project_cards(active, selected)
            results = [html.H2("Projects"), html.Div(listing, className="project-grid")]
        elif view == "kanban":
            if project not in index.projects:
                results = [html.H2("Project not found"), html.P("Choose a project from the sidebar.")]
            else:
                limit = (board_limit.get("limit") if isinstance(board_limit, dict)
                         and board_limit.get("project") == project
                         and (board_limit.get("limit") is None or type(board_limit.get("limit")) is int
                              and board_limit["limit"] >= BOARD_PAGE_SIZE) else BOARD_PAGE_SIZE)
                results = [project_note_panel(projects_dir, project, links, index.sources),
                            html.H2(f"{project} · {len(selected)} tasks"),
                             *kanban_board(selected, links, allow_writes, index.lanes.get(project, ()),
                                           sort_by or "due", active.tasks, index.sources, limit)]
        elif view == "reference":
            results = [html.H2(f"Reference · {len(hidden)} files · {len(selected)} tasks"),
                       html.P("Hidden notes remain in their original files and can be opened in Obsidian.", className="hint"),
                       html.Ul([html.Li(html.A(source, href=links.for_note(source), target="_blank",
                                               rel="noopener noreferrer", className="source-link")) for source in hidden],
                               className="reference-files"),
                       *task_table(selected, links, False, index.sources, table_sort)]
        else:
            results = [html.H2(f"{view.title()} · {len(selected)}"),
                       *task_table(selected, links, allow_writes, index.sources, table_sort)]
        diagnostics = [html.P(f"{index.files} files scanned · {len(index.tasks)} tasks · {len(index.warnings)} warnings")]
        if index.warnings:
            diagnostics.append(html.Details([
                html.Summary("Parsing warnings"),
                html.Ul([html.Li(f"{w.source}{':' + str(w.line) if w.line else ''}: {w.message}")
                         for w in index.warnings[:100]]),
            ]))
        return (sidebar(active, view, project, today, allow_writes), title,
                summary(active, today) if view == "projects" else [], results, diagnostics,
                {} if view in ("projects", "reference") else {"display": "none"},
                 f"Manage visibility · {len(hidden)} files · {len(hidden_tasks)} tasks",
                 "File/folder rules: " + (", ".join(rules.reference_globs) or "none")
                 + " · Task rules: " + (", ".join(rules.task_globs) or "none"))

    @app.callback(Output("board-sort-control", "style"), Input("url", "search"))
    def show_board_sort(search: str | None):
        return {} if route(search)[0] == "kanban" else {"display": "none"}

    @app.callback(Output("board-limit", "data"), Input({"type": "board-page", "action": ALL}, "n_clicks"),
                  State("url", "search"), State("board-limit", "data"), prevent_initial_call=True)
    def expand_board(_clicks, search, current):
        triggered = ctx.triggered_id
        view, project = route(search)
        if (not isinstance(triggered, dict) or triggered.get("action") not in ("more", "all")
                or not any(_clicks or []) or view != "kanban" or not project):
            return no_update
        previous = (current.get("limit") if isinstance(current, dict) and current.get("project") == project
                    and type(current.get("limit")) is int and current["limit"] >= BOARD_PAGE_SIZE
                    else BOARD_PAGE_SIZE)
        return {"project": project, "limit": None if triggered["action"] == "all"
                else previous + BOARD_PAGE_SIZE}

    @app.callback(Output("table-sort", "data"), Input({"type": "table-sort", "column": ALL}, "n_clicks"),
                  State("table-sort", "data"), prevent_initial_call=True)
    def choose_table_sort(_clicks, current):
        triggered = ctx.triggered_id
        if not isinstance(triggered, dict) or not any(_clicks or []):
            return no_update
        chosen = triggered.get("column")
        if not isinstance(chosen, str) or chosen not in dict(TABLE_COLUMNS):
            return no_update
        previous, direction = table_sort_choice(current)
        if chosen == previous:
            direction = "desc" if direction == "asc" else "asc"
        else:
            direction = "desc" if chosen == "priority" else "asc"
        return {"column": chosen, "direction": direction}

    @app.callback(Output("visibility-panel", "open"), Input("url", "search"))
    def open_visibility_on_reference(search: str | None):
        return route(search)[0] == "reference"

    if allow_writes:
        assert writer is not None

        @app.callback(Output("visibility-proposal", "data"), Output("visibility-revision", "data"),
                      Output("visibility-status", "children"),
                      Input("preview-visibility", "n_clicks"), Input("confirm-visibility", "n_clicks"),
                      Input("cancel-visibility", "n_clicks"),
                      State("visibility-kind", "value"), State("visibility-action", "value"),
                      State("visibility-pattern", "value"),
                      State("visibility-proposal", "data"), State("visibility-revision", "data"),
                      prevent_initial_call=True)
        def change_visibility(_preview, _confirm, _cancel, kind, action, pattern, proposal, revision):
            if ctx.triggered_id == "cancel-visibility":
                return None, no_update, "Reference change cancelled."
            try:
                if ctx.triggered_id == "preview-visibility":
                    if kind not in ("file", "task"):
                        raise VisibilityError("Choose files/folders or tasks")
                    entered = pattern
                    pattern = (file_rule_from_input(pattern, projects_dir) if kind == "file"
                               else validate_task_pattern(pattern))
                    before, digest = load_rules(visibility_file)
                    existing = before.reference_globs if kind == "file" else before.task_globs
                    if action == "add" and pattern not in existing:
                        updated = (*existing, pattern)
                    elif action == "remove" and pattern in existing:
                        updated = tuple(item for item in existing if item != pattern)
                    else:
                        raise VisibilityError("Select a new glob to hide or an existing rule to remove")
                    after = (replace(before, reference_globs=updated) if kind == "file"
                             else replace(before, task_globs=updated))
                    affected = changed_visibility(scan(projects_dir, excludes), before, after)
                    return {"before": before.as_dict(), "after": after.as_dict(), "digest": digest,
                            "affected": affected, "kind": kind, "entered": entered,
                            "pattern": pattern, "action": action}, (
                        no_update), "Review affected notes and tasks before confirming."
                if ctx.triggered_id == "confirm-visibility":
                    normalized = (file_rule_from_input(pattern, projects_dir) if kind == "file"
                                  else validate_task_pattern(pattern))
                    if (not isinstance(proposal, dict) or kind != proposal.get("kind")
                            or action != proposal.get("action") or pattern != proposal.get("entered")
                            or normalized != proposal.get("pattern")):
                        raise VisibilityError("Rule changed; review again")
                    pattern = normalized
                    before, digest = load_rules(visibility_file)
                    if digest != proposal.get("digest") or before.as_dict() != proposal["before"]:
                        raise VisibilityError("Visibility rules changed; review again")
                    existing = before.reference_globs if kind == "file" else before.task_globs
                    if action == "add" and pattern not in existing:
                        updated = (*existing, pattern)
                    elif action == "remove" and pattern in existing:
                        updated = tuple(item for item in existing if item != pattern)
                    else:
                        raise VisibilityError("Rule changed; review again")
                    after = (replace(before, reference_globs=updated) if kind == "file"
                             else replace(before, task_globs=updated))
                    if after.as_dict() != proposal["after"]:
                        raise VisibilityError("Rule changed; review again")
                    affected = changed_visibility(scan(projects_dir, excludes), before, after)
                    if affected != proposal["affected"]:
                        raise VisibilityError("Matching files changed; review again")
                    save_rules(visibility_file, after, digest)
                    return None, (revision or 0) + 1, "Reference rule saved. No Markdown files changed."
            except (VisibilityError, ValueError, KeyError, TypeError) as exc:
                return None, no_update, f"No rule saved: {exc}"
            return no_update, no_update, no_update

        @app.callback(Output("visibility-dialog", "style"), Output("visibility-diff", "children"),
                      Input("visibility-proposal", "data"))
        def show_visibility(proposal):
            if not isinstance(proposal, dict):
                return {"display": "none"}, ""
            try:
                action = proposal["action"]
                if action not in ("add", "remove") or proposal["kind"] not in ("file", "task"):
                    raise ValueError("Invalid action")
                affected = proposal["affected"]
                if (not isinstance(affected, dict) or set(affected) != {"files", "tasks"}
                        or any(not isinstance(items, list) or any(not isinstance(item, str) for item in items)
                               for items in affected.values())):
                    raise ValueError("Invalid preview")
                before, after = proposal["before"], proposal["after"]
                if (not isinstance(before, dict) or not isinstance(after, dict)
                        or any(set(item) != {"reference_globs", "task_globs"} for item in (before, after))
                        or any(not isinstance(values, list) or any(not isinstance(value, str) for value in values)
                               for values in [*before.values(), *after.values()])):
                    raise ValueError("Invalid rules")

                def labels(rules):
                    return (f"Files: {', '.join(rules['reference_globs']) or '(none)'}; "
                            f"Tasks: {', '.join(rules['task_globs']) or '(none)'}")
                changes = [f"Files changing visibility ({len(affected['files'])}):",
                           *(affected["files"] or ["(none)"]),
                           f"Tasks changing visibility ({len(affected['tasks'])}):",
                           *(affected["tasks"] or ["(none)"])]
                return {}, (f"Before rules: {labels(before)}\n"
                            f"After rules:  {labels(after)}\n\n"
                            f"Input: {proposal.get('entered', '')}\n"
                            f"{'Hide' if action == 'add' else 'Restore'} with rule: {proposal['pattern']}\n"
                            + "\n".join(changes))
            except (KeyError, ValueError):
                return {"display": "none"}, ""

        def selected_task(selected):
            handle = EditHandle.from_dict(selected)
            task = next((item for item in scan(projects_dir, excludes).tasks
                         if item.source == handle.source and item.line == handle.line
                         and item.original == handle.original and item.file_digest == handle.digest), None)
            if task is None:
                raise StaleSnapshot("Task changed; refresh and retry")
            return task

        @app.callback(Output("edit-task-context", "children"), Input("edit-selected", "data"))
        def show_task_context(selected):
            if not selected:
                return []
            try:
                task = selected_task(selected)
                index = scan(projects_dir, excludes)
                return task_detail_context(task, index.tasks, links, index.sources)
            except EditError:
                return []

        @app.callback(Output("edit-lane", "options"), Output("edit-lane", "disabled"),
                      Output("new-lane-controls", "style"),
                      Input("edit-selected", "data"), Input("lane-revision", "data"))
        def lane_choices(selected, _revision):
            if not selected:
                return [], True, {"display": "none"}
            try:
                task = selected_task(selected)
            except EditError:
                return [], True, {"display": "none"}
            if task.parent_line is not None or (task.is_board and task.board_source != task.source):
                return [{"label": task_column(task), "value": task_column(task)}], True, {"display": "none"}
            choices = (task.lanes if task.is_board else tuple(dict.fromkeys(("Backlog", *task.lanes))))
            board = scan(projects_dir, excludes).boards.get(task.project)
            options = [{"label": name, "value": name} for name in choices]
            if task_column(task) not in choices:
                options.append({"label": task_column(task), "value": task_column(task), "disabled": True})
            return (options, False,
                    {} if board else {"display": "none"})

        @app.callback(
            Output("lane-proposal", "data"), Output("lane-revision", "data"), Output("lane-status", "children"),
            Output("edit-selected", "data", allow_duplicate=True),
            Input("preview-lane", "n_clicks"), Input("confirm-lane", "n_clicks"), Input("cancel-lane", "n_clicks"),
            State("edit-selected", "data"), State("new-lane-name", "value"),
            State("lane-proposal", "data"), State("lane-revision", "data"),
            prevent_initial_call=True,
        )
        def create_lane(_preview, _confirm, _cancel, selected, name, proposal, revision):
            try:
                if ctx.triggered_id == "cancel-lane":
                    return None, no_update, "Lane creation cancelled.", no_update
                if ctx.triggered_id == "preview-lane":
                    project = selected_task(selected).project
                    preview, digest = writer.preview_create_lane(project, name)
                    return {"project": project, "name": name, "digest": digest,
                            "source": preview.source, "before": preview.before, "after": preview.after}, (
                        no_update), "Review the new board heading before confirming.", no_update
                if ctx.triggered_id == "confirm-lane":
                    task = selected_task(selected)
                    if not isinstance(proposal, dict) or task.project != proposal.get("project"):
                        raise InvalidEdit("Review a lane for the selected project first")
                    writer.apply_create_lane(proposal["project"], proposal["name"],
                                             proposal["digest"], proposal["after"])
                    if task.is_board:
                        return None, (revision or 0) + 1, "Lane created. Reopen the board task to move it.", None
                    return None, (revision or 0) + 1, "Lane created. Select it in the task editor to move the task.", no_update
            except (EditError, KeyError, TypeError) as exc:
                return None, no_update, f"No lane created: {exc}", no_update
            return no_update, no_update, no_update, no_update

        @app.callback(Output("lane-panel", "style"), Output("lane-selection", "children"),
                      Output("lane-diff", "children"), Input("lane-proposal", "data"))
        def show_lane(proposal):
            if not isinstance(proposal, dict):
                return {"display": "none"}, "", ""
            try:
                if not all(isinstance(proposal[key], str) for key in ("source", "before", "after")):
                    raise InvalidEdit("Invalid lane preview")
            except (EditError, KeyError):
                return {"display": "none"}, "", ""
            return {}, proposal["source"], f"Before: {proposal['before']}\nAfter:  {proposal['after']}"

        @app.callback(
            Output("move-proposal", "data"), Output("move-revision", "data"), Output("move-status", "children"),
            Input("move-request", "data"), Input("confirm-move", "n_clicks"), Input("cancel-move", "n_clicks"),
            State("move-proposal", "data"), State("move-revision", "data"),
            prevent_initial_call=True,
        )
        def move(request, _confirm, _cancel, proposal, revision):
            try:
                if ctx.triggered_id == "cancel-move":
                    return None, no_update, "Move cancelled."
                if ctx.triggered_id == "move-request":
                    if not isinstance(request, dict):
                        raise InvalidEdit("Invalid move request")
                    handle = EditHandle.from_dict(json.loads(request["key"]))
                    destination = request.get("destination")
                    preview = writer.preview_move(handle, destination)
                    return {"handle": handle.as_dict(), "destination": destination,
                            "before": preview.before, "after": preview.after}, no_update, "Review the move before confirming."
                if ctx.triggered_id == "confirm-move":
                    if not isinstance(proposal, dict):
                        raise InvalidEdit("Drop a task into a lane first")
                    handle = EditHandle.from_dict(proposal["handle"])
                    writer.apply_move(handle, proposal["destination"], proposal["after"])
                    return None, (revision or 0) + 1, f"Moved {handle.source}; refresh Obsidian if it is open."
            except (EditError, ValueError, KeyError, TypeError) as exc:
                return None, no_update, f"No move applied: {exc}"
            return no_update, no_update, no_update

        @app.callback(Output("move-panel", "style"), Output("move-selection", "children"),
                      Output("move-diff", "children"),
                      Input("move-proposal", "data"))
        def show_move(proposal):
            if not isinstance(proposal, dict):
                return {"display": "none"}, "", ""
            try:
                handle = EditHandle.from_dict(proposal["handle"])
                if not isinstance(proposal["before"], str) or not isinstance(proposal["after"], str):
                    raise InvalidEdit("Invalid move preview")
                destination = proposal["destination"]
            except (EditError, KeyError):
                return {"display": "none"}, "", ""
            return {}, f"{handle.source}:{handle.line} → {destination}", (
                f"Before: {proposal['before']}\nAfter:  {proposal['after']}")

        @app.callback(
            Output("edit-selected", "data"), Output("edit-proposal", "data"),
            Output("edit-revision", "data"), Output("edit-status", "children"),
            Input({"type": "edit-task", "key": ALL}, "n_clicks"),
            Input({"type": "quick-due", "key": ALL}, "value"),
            Input("review-edit", "n_clicks"), Input("confirm-edit", "n_clicks"), Input("cancel-edit", "n_clicks"),
            State("edit-selected", "data"), State("edit-proposal", "data"),
            *[State(form_id(name), "value") for name in FORM_FIELDS],
            State("edit-lane", "value"),
            State({"type": "quick-due", "key": ALL}, "id"), State("edit-revision", "data"),
            prevent_initial_call=True,
        )
        def edit(_buttons, quick_dates, _review, _confirm, _cancel, selected, proposal, *states):
            form = dict(zip(FORM_FIELDS, (value or "" for value in states[:len(FORM_FIELDS)])))
            selected_lane, quick_ids, revision = states[-3:]
            triggered = ctx.triggered_id
            if isinstance(triggered, dict):
                try:
                    handle = EditHandle.from_dict(json.loads(triggered["key"]))
                except (EditError, ValueError, TypeError):
                    return None, None, no_update, "Invalid task reference. Refresh the dashboard."
                if triggered["type"] == "quick-due":
                    chosen = next((value for identity, value in zip(quick_ids or [], quick_dates or [])
                                   if identity == triggered), None)
                    original_due = DUE.search(handle.original)
                    if not chosen or (original_due and chosen == original_due.group(1)):
                        return no_update, no_update, no_update, no_update
                    try:
                        fields = writer.fields_for(handle.original)
                        fields["due"] = chosen
                        lane = task_column(selected_task(handle.as_dict()))
                        preview = writer.preview_change(handle, fields, lane)
                        data = {"handle": handle.as_dict(), "fields": fields,
                                "lane": lane, "preview_type": "quick-due", "before": preview.before, "after": preview.after}
                        return handle.as_dict(), data, no_update, "Review the date change before confirming."
                    except StaleSnapshot as exc:
                        return None, None, (revision or 0) + 1, f"No change applied: {exc}"
                    except EditError as exc:
                        return None, None, (revision or 0) + 1, f"No change applied: {exc}"
                if triggered["type"] != "edit-task" or not any(_buttons or []):
                    return no_update, no_update, no_update, no_update
                try:
                    writer.fields_for(handle.original)
                except EditError as exc:
                    return None, None, no_update, f"Edit this task in Obsidian: {exc}"
                return handle.as_dict(), None, no_update, "Edit the fields, then review the exact Markdown change."
            if triggered == "cancel-edit":
                return None, None, (revision or 0) + 1, "Edit cancelled."
            if not selected:
                return no_update, no_update, no_update, ""
            try:
                handle = EditHandle.from_dict(selected)
                if triggered == "review-edit":
                    form["id"] = writer.fields_for(handle.original)["id"]
                    preview = writer.preview_change(handle, form, selected_lane)
                    data = {"handle": selected, "fields": form, "lane": selected_lane,
                            "before": preview.before, "after": preview.after}
                    return no_update, data, no_update, "Preview ready. Review the change before confirming."
                if triggered == "confirm-edit":
                    if not isinstance(proposal, dict) or proposal.get("handle") != selected:
                        raise InvalidEdit("Review the selected task before confirming")
                    form["id"] = writer.fields_for(handle.original)["id"]
                    if proposal.get("fields") != form or proposal.get("lane") != selected_lane:
                        raise InvalidEdit("Fields changed; review again before confirming")
                    result = writer.apply_change(handle, proposal["fields"], proposal["lane"], proposal.get("after"))
                    return None, None, (revision or 0) + 1, f"Saved {result.source}:{result.line}."
            except StaleSnapshot as exc:
                return None, None, (revision or 0) + 1, f"No change applied: {exc}"
            except UncertainWrite as exc:
                return None, None, (revision or 0) + 1, f"Inspect the note before retrying: {exc}"
            except EditError as exc:
                return no_update, None, no_update, f"No change applied: {exc}"
            return no_update, no_update, no_update, no_update

        @app.callback(*[Output(form_id(name), "value") for name in FORM_FIELDS], Output("edit-lane", "value"),
                      Input("edit-selected", "data"), State("edit-proposal", "data"))
        def prefill_form(selected, proposal):
            fields = {}
            lane = None
            try:
                if selected:
                    handle = EditHandle.from_dict(selected)
                    fields = writer.fields_for(handle.original)
                    lane = task_column(selected_task(selected))
                    if (isinstance(proposal, dict) and proposal.get("handle") == selected
                            and proposal.get("preview_type") == "quick-due"):
                        fields["due"] = proposal["fields"]["due"]
                        lane = proposal["lane"]
            except EditError:
                pass
            return (*tuple(fields.get(name, "normal" if name == "priority" else "todo" if name == "status" else "")
                           for name in FORM_FIELDS), lane)

        @app.callback(
            Output("edit-panel", "style"), Output("edit-selection", "children"),
            Output("edit-diff", "children"), Output("confirm-edit", "disabled"),
            Input("edit-selected", "data"), Input("edit-proposal", "data"),
            *[Input(form_id(name), "value") for name in FORM_FIELDS],
            Input("edit-lane", "value"),
        )
        def show_preview(selected, proposal, *values):
            if not selected:
                return {"display": "none"}, "", "", True
            try:
                handle = EditHandle.from_dict(selected)
            except EditError:
                return {"display": "none"}, "", "", True
            location = f"{handle.source}:{handle.line}"
            try:
                source = task_link(location, selected_task(selected), links, "source-link")
            except EditError:
                source = location
            if (not isinstance(proposal, dict) or proposal.get("handle") != selected
                    or not isinstance(proposal.get("before"), str)
                    or not isinstance(proposal.get("after"), str)):
                return {}, source, "Change the task, then review the exact before/after line.", True
            form = dict(zip(FORM_FIELDS, (value or "" for value in values)))
            form["id"] = writer.fields_for(handle.original)["id"]
            if form != proposal.get("fields") or values[-1] != proposal.get("lane"):
                return {}, source, "Fields changed; review changes again before confirming.", True
            return {}, source, f"Before: {proposal['before']}\nAfter:  {proposal['after']}", False

    return app
