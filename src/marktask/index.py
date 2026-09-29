"""Discover project Markdown and build a disposable, read-only task index."""

from __future__ import annotations

import os
import re
import hashlib
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from pathlib import Path


TASK = re.compile(r"^\s*[-*+]\s+\[([ xX-])\]\s*(.*)$")
LIST_NOTE = re.compile(r"^(\s*)[-*+]\s+(?!\[[ xX-]\])(.+)$")
HEADING = re.compile(r"^\s*##\s+(.+?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
DUE = re.compile(r"📅\s*(\S+)")
RECURRENCE = re.compile(r"🔁\s*([^📅✅]+)")
TAG = re.compile(r"(?<![\w\]/])#([\w/-]+)")
ROOT_PROJECT = "(root)"
DEFAULT_EXCLUDES = (".git", ".obsidian", "attachments", "generated")
DEFAULT_LANES = ("Inbox", "Backlog", "To Do", "Next", "In Progress", "Waiting", "Review", "Done")
PRIORITY_MARKERS = {"🔺": "highest", "⏫": "high", "🔼": "medium", "🔽": "low", "⏬": "lowest"}
PRIORITY_RANK = {"lowest": 0, "low": 1, "normal": 2, "medium": 3, "high": 4, "highest": 5}


@dataclass(frozen=True)
class Task:
    project: str
    source: str  # Relative to the selected Projects directory
    line: int
    text: str
    original: str
    completed: bool
    column: str | None
    due: date | None
    recurrence: str | None
    tags: tuple[str, ...]
    file_digest: str = ""  # Empty for standalone parser use; scan() supplies the full-file snapshot.
    cancelled: bool = False
    lanes: tuple[str, ...] = ()
    is_board: bool = False
    board_source: str | None = None
    priority: str = "normal"
    parent_line: int | None = None
    notes: tuple[str, ...] = ()
    parent_lane: str | None = None


@dataclass(frozen=True)
class Warning:
    source: str
    line: int | None
    message: str


@dataclass(frozen=True)
class Index:
    projects: tuple[str, ...]
    files: int
    tasks: tuple[Task, ...]
    warnings: tuple[Warning, ...]
    boards: dict[str, str] = field(default_factory=dict)  # Project -> relative _Kanban note path.
    lanes: dict[str, tuple[str, ...]] = field(default_factory=dict)
    sources: tuple[str, ...] = ()


def lane_slug(name: str) -> str:
    return re.sub(r"[^\w]+", "-", name.casefold()).strip("-")


def board_sections(content: str) -> tuple[tuple[str, int], ...] | None:
    """Return (heading, zero-based line) for a board; ignore headings in comments/fences."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if end is None or not any(re.fullmatch(r"kanban-plugin:\s*board", line.strip()) for line in lines[1:end]):
        return None
    columns: list[tuple[str, int]] = []
    fence_char = ""
    fence_size = 0
    in_comment = False
    for number, line in enumerate(lines[end + 1:], end + 1):
        stripped = line.strip()
        if in_comment:
            if "%%" in stripped:
                in_comment = False
            continue
        if stripped.startswith("%%"):
            if stripped.count("%%") < 2:
                in_comment = True
            continue
        fence = FENCE.match(line)
        if fence:
            marker = fence.group(1)
            if not fence_char:
                fence_char, fence_size = marker[0], len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_size and stripped == marker:
                fence_char = ""
            continue
        if not fence_char and (heading := HEADING.match(line)):
            columns.append((heading.group(1).strip(), number))
    return tuple(columns)


def board_columns(content: str) -> tuple[str, ...] | None:
    sections = board_sections(content)
    return None if sections is None else tuple(name for name, _ in sections)


def parse_markdown(content: str, source: str, project: str, file_digest: str = "") -> tuple[list[Task], list[Warning]]:
    """Recognize Markdown checkboxes; board headings are statuses only on Kanban boards."""
    lines = content.splitlines()
    tasks: list[Task] = []
    warnings: list[Warning] = []
    frontmatter_end = 0
    board = False

    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                frontmatter_end = i + 1
                board = any(re.match(r"^kanban-plugin:\s*board\s*$", item.strip()) for item in lines[1:i])
                break
        else:
            warnings.append(Warning(source, 1, "unclosed frontmatter; file skipped"))
            return tasks, warnings

    fence_char = ""
    fence_size = 0
    in_comment = False
    column: str | None = None
    task_stack: list[tuple[int, int]] = []  # (indentation, index in tasks)
    for number, line in enumerate(lines[frontmatter_end:], start=frontmatter_end + 1):
        stripped = line.strip()
        if in_comment:
            if "%%" in stripped:
                in_comment = False
            continue
        if stripped.startswith("%%"):
            if stripped.count("%%") < 2:
                in_comment = True
            continue
        fence = FENCE.match(line)
        if fence:
            marker = fence.group(1)
            if not fence_char:
                fence_char, fence_size = marker[0], len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_size and stripped == marker:
                fence_char = ""
            continue
        if fence_char:
            continue
        heading = HEADING.match(line)
        if board and heading:
            column = heading.group(1).strip()
            task_stack.clear()
            continue
        match = TASK.match(line)
        if not match:
            note = LIST_NOTE.match(line)
            if note:
                indent = len(note.group(1).expandtabs(4))
                while task_stack and task_stack[-1][0] >= indent:
                    task_stack.pop()
                if task_stack:
                    parent_index = task_stack[-1][1]
                    parent = tasks[parent_index]
                    tasks[parent_index] = replace(parent, notes=(*parent.notes, note.group(2).strip()))
            elif stripped and not line[0].isspace():
                task_stack.clear()
            continue
        indent = len(line[:len(line) - len(line.lstrip(" \t"))].expandtabs(4))
        while task_stack and task_stack[-1][0] >= indent:
            task_stack.pop()
        parent_line = tasks[task_stack[-1][1]].line if task_stack else None
        text = match.group(2).strip()
        due: date | None = None
        date_match = DUE.search(text)
        if date_match:
            token = date_match.group(1)
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", token):
                try:
                    due = date.fromisoformat(token)
                except ValueError:
                    pass
            if due is None:
                warnings.append(Warning(source, number, "invalid due date"))
        repeat = RECURRENCE.search(text)
        recurrence = repeat.group(1).strip() if repeat else None
        priority_tokens = re.findall(r"(?<!\S)(🔺|⏫|🔼|🔽|⏬)(?=\s|$)", text)
        tasks.append(Task(
            project=project,
            source=source,
            line=number,
            text=text,
            original=line,
            completed=match.group(1).lower() == "x",
            cancelled=match.group(1) == "-",
            column=column,
            due=due,
            recurrence=recurrence,
            tags=tuple(TAG.findall(text)),
            file_digest=file_digest,
            is_board=board,
            priority=PRIORITY_MARKERS[priority_tokens[0]] if len(priority_tokens) == 1 else "normal",
            parent_line=parent_line,
        ))
        task_stack.append((indent, len(tasks) - 1))
    if fence_char:
        warnings.append(Warning(source, None, "unclosed code fence"))
    return tasks, warnings


def scan(projects_dir: Path, excludes: tuple[str, ...] = DEFAULT_EXCLUDES) -> Index:
    """Scan exactly the selected tree, without following directory or file symlinks."""
    if not projects_dir.is_dir():
        raise ValueError("Projects path does not exist or is not a directory")
    excluded = set(excludes)
    projects: set[str] = set()
    tasks: list[Task] = []
    warnings: list[Warning] = []
    files = 0
    documents: list[tuple[str, str, bytes]] = []
    folders: set[str] = set()
    for directory, dirs, names in os.walk(projects_dir, followlinks=False):
        here = Path(directory)
        relative_dir = here.relative_to(projects_dir)
        dirs[:] = sorted(d for d in dirs if d not in excluded and not (here / d).is_symlink())
        if relative_dir == Path("."):
            projects.update(dirs)
        else:
            folders.add(relative_dir.as_posix())
        for name in sorted(names):
            path = here / name
            if name in excluded or path.suffix.lower() != ".md" or path.is_symlink():
                continue
            relative = path.relative_to(projects_dir)
            source = relative.as_posix()
            project = relative.parts[0] if len(relative.parts) > 1 else ROOT_PROJECT
            projects.add(project)
            files += 1
            try:
                data = path.read_bytes()
                content = data.decode("utf-8-sig")
            except (OSError, UnicodeError):
                warnings.append(Warning(source, None, "unable to read UTF-8 Markdown"))
                continue
            documents.append((source, content, data))
    # A nested folder with its own master note is a project, not part of the parent project.
    masters: set[str] = set()
    for folder in folders:
        candidates = [Path(source).name for source, _content, _data in documents
                      if str(Path(source).parent) == folder and Path(source).name.startswith("_")
                      and not Path(source).name.casefold().startswith("_kanban")]
        if f"_{Path(folder).name}.md" in candidates or len(candidates) == 1:
            masters.add(folder)
        if "/" in folder and folder in masters:
            projects.add(folder)

    boards: dict[str, str] = {}
    lanes: dict[str, tuple[str, ...]] = {}
    for project in sorted(projects):
        if project not in masters:
            continue
        candidates = [(source, columns) for source, content, _ in documents
                      if str(Path(source).parent) == project and Path(source).name.casefold().startswith("_kanban")
                      if (columns := board_columns(content)) is not None]
        if len(candidates) > 1:
            warnings.append(Warning(project, None, "multiple project Kanban boards; lanes are ambiguous"))
            continue
        if candidates:
            source, columns = candidates[0]
            slugs = [lane_slug(name) for name in columns]
            if not columns or any(not slug for slug in slugs) or len(set(slugs)) != len(slugs):
                warnings.append(Warning(source, None, "empty or duplicate Kanban lanes; board moves disabled"))
                continue
            boards[project] = source
            lanes[project] = columns

    for source, content, data in documents:
        folder = Path(source).parent
        parents = (folder.as_posix(), *(p.as_posix() for p in folder.parents))
        project = next((name for name in parents if name in projects), ROOT_PROJECT)
        parsed, issues = parse_markdown(content, source, project, hashlib.sha256(data).hexdigest())
        active = boards.get(project) == source
        project_lanes = lanes.get(project, DEFAULT_LANES)
        by_line: dict[int, Task] = {}
        for task in parsed:
            parent = by_line.get(task.parent_line) if task.parent_line is not None else None
            indexed = replace(task, column=task.column if active else None,
                              board_source=source if active else None, lanes=project_lanes,
                              parent_lane=task_column(parent) if parent is not None else None)
            tasks.append(indexed)
            by_line[task.line] = indexed
        warnings.extend(issues)
        if parsed and parsed[0].is_board and not active:
            warnings.append(Warning(source, None, "board is not paired with this project's master note; native lanes ignored"))
    return Index(tuple(sorted(projects)), files, tuple(tasks), tuple(warnings), boards, lanes,
                 tuple(source for source, _content, _data in documents))


def visible_tasks(tasks: tuple[Task, ...], view: str, today: date) -> list[Task]:
    """Upcoming means tomorrow through seven days from today, inclusive."""
    open_tasks = (task for task in tasks if not task.completed and not task.cancelled)
    if view == "today":
        selected = [task for task in open_tasks if task.due == today]
    elif view == "inbox":
        selected = [task for task in open_tasks if task_column(task).casefold() == "inbox"]
    elif view == "overdue":
        selected = [task for task in open_tasks if task.due is not None and task.due < today]
    elif view == "upcoming":
        selected = [task for task in open_tasks if task.due is not None and today < task.due <= today + timedelta(days=7)]
    elif view == "waiting":
        selected = [task for task in open_tasks if task_column(task).casefold() == "waiting"]
    else:
        selected = list(tasks)
    return sorted(selected, key=lambda task: (task.due or date.max, task.project, task.source, task.line))


def priority_rank(task: Task) -> int:
    return PRIORITY_RANK[task.priority]


def task_column(task: Task) -> str:
    """Use completion, then native Kanban column, then known workflow tags."""
    if task.cancelled:
        return "Cancelled"
    if task.completed:
        return "Done"
    if task.parent_lane:
        return task.parent_lane
    if task.column:
        return task.column
    if task.lanes:
        matching = [lane for lane in task.lanes if lane_slug(lane) in
                    {tag[5:].casefold() for tag in task.tags if tag.startswith("todo/")}]
        if len(matching) == 1:
            return matching[0]
        if len(matching) > 1:
            return "Backlog"  # Ambiguous tags are not silently assigned to a lane.
        if "todo" in task.tags:
            return "Backlog"
        labels = {tag.split("/", 1)[0].casefold() for tag in task.tags}
        for tags, column in (({"inbox"}, "Inbox"), ({"waiting", "blocked"}, "Waiting"),
                             ({"doing", "in-progress"}, "In Progress"), ({"next"}, "Next")):
            if labels & tags and column in task.lanes:
                return column
        return "Backlog"
    labels = {tag.split("/", 1)[0].casefold() for tag in task.tags}
    for tags, column in (
        ({"inbox"}, "Inbox"),
        ({"waiting", "blocked"}, "Waiting"),
        ({"doing", "in-progress"}, "In Progress"),
        ({"next"}, "Next"),
        ({"todo", "to-do"}, "To Do"),
    ):
        if labels & tags:
            return column
    return "Backlog"
