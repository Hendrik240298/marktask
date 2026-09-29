"""Guarded single-line Markdown edits. Never call this on a real vault as a test fixture."""

from __future__ import annotations

import hashlib
import os
import re
import stat
import tempfile
import threading
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path, PurePosixPath

from marktask.index import (DEFAULT_EXCLUDES, DUE, TAG, TASK, Task, board_sections,
                            lane_slug, parse_markdown, scan, task_column)


class EditError(Exception):
    """Base class for errors safe to show in the editing UI."""


class StaleSnapshot(EditError):
    """The note changed since the dashboard displayed the task."""


class UnsupportedTask(EditError):
    """This task syntax or requested edit is not safely supported."""


class InvalidEdit(EditError):
    """The proposed path, snapshot or date is invalid."""


class FileAccessError(EditError):
    """The source could not be safely read or written."""


class UncertainWrite(EditError):
    """Replacement happened, but its final durability could not be confirmed."""


@dataclass(frozen=True)
class EditHandle:
    source: str
    line: int
    original: str
    digest: str

    @classmethod
    def from_task(cls, task: Task) -> EditHandle:
        if not task.file_digest:
            raise InvalidEdit("Task has no scanned file snapshot")
        return cls(task.source, task.line, task.original, task.file_digest)

    @classmethod
    def from_dict(cls, value: object) -> EditHandle:
        if not isinstance(value, dict):
            raise InvalidEdit("Invalid task reference")
        source, line = value.get("source"), value.get("line")
        original, digest = value.get("original"), value.get("digest")
        if (not isinstance(source, str) or type(line) is not int or line < 1
                or not isinstance(original, str) or "\n" in original or "\r" in original
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise InvalidEdit("Invalid task reference")
        return cls(source, line, original, digest)

    def as_dict(self) -> dict:
        return {"source": self.source, "line": self.line, "original": self.original, "digest": self.digest}


@dataclass(frozen=True)
class EditPreview:
    before: str
    after: str
    source: str
    line: int


@dataclass(frozen=True)
class _Prepared:
    preview: EditPreview
    original_bytes: bytes
    updated_bytes: bytes
    device: int
    inode: int
    mode: int


TRAILING_BLOCK = re.compile(r"\s+\^[A-Za-z0-9-]+\s*$")
DATE_MARKERS = {"due": "📅", "scheduled": "⏳", "start": "🛫", "created": "➕",
                "done": "✅", "cancelled": "❌"}
PRIORITIES = {"normal": "", "lowest": "⏬", "low": "🔽", "medium": "🔼", "high": "⏫", "highest": "🔺"}
MARKERS = "📅|⏳|🛫|➕|✅|❌|🔁|🔺|⏫|🔼|🔽|⏬|🆔|⛔|🏁"
TITLE_METADATA = re.compile(rf"(?<!\S)(?=(?:{MARKERS})(?=\s|$)|#[\w/-]+(?=\s|$)|\^[A-Za-z0-9-]+(?=\s|$))")
RECURRENCE_FIELD = re.compile(
    rf"(?<!\S)🔁[ \t]+(.+?)(?=(?:[ \t]+(?:{MARKERS}|#[\w/-]+|\^[A-Za-z0-9-]+)(?=\s|$))|$)"
)
DEPENDENCY_FIELD = re.compile(r"(?<!\S)⛔[ \t]+([A-Za-z0-9_-]+(?:,[ \t]*[A-Za-z0-9_-]+)*)(?=\s|$)")
ID_FIELD = re.compile(r"(?<!\S)🆔[ \t]+([A-Za-z0-9_-]+)(?=\s|$)")
TAG_TOKEN = re.compile(r"(?<!\S)#[\w/-]+(?=\s|$)")
RECURRENCE_RULE = re.compile(
    r"every (?:weekday|day|week|month|year|[1-9]\d* (?:days|weeks|months|years))(?: when done)?", re.I
)
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for(path: Path) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(str(path), threading.Lock())


class TaskWriter:
    def __init__(self, projects_dir: Path, excludes: tuple[str, ...] = DEFAULT_EXCLUDES):
        self.root = projects_dir.absolute()
        self.excludes = set(excludes)

    def _path(self, handle: EditHandle) -> Path:
        source = PurePosixPath(handle.source)
        if (not handle.source or source.is_absolute() or any(part in ("", ".", "..") for part in handle.source.split("/"))
                or "\\" in handle.source or "\x00" in handle.source or source.suffix.lower() != ".md"
                or any(part in self.excludes for part in source.parts)):
            raise InvalidEdit("Task path is outside the allowed Markdown files")
        path = self.root
        for position, part in enumerate(source.parts):
            path = path / part
            try:
                mode = path.lstat().st_mode
            except FileNotFoundError as exc:
                raise StaleSnapshot("Source file is no longer present; refresh") from exc
            except OSError as exc:
                raise FileAccessError("Cannot inspect the source path") from exc
            if stat.S_ISLNK(mode):
                raise InvalidEdit("Editing through a symlink is disabled")
            if position < len(source.parts) - 1 and not stat.S_ISDIR(mode):
                raise InvalidEdit("Source parent is not a directory")
        return path

    @staticmethod
    def _read(path: Path) -> tuple[bytes, os.stat_result]:
        try:
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(fd, "rb") as file:
                info = os.fstat(file.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise UnsupportedTask("Only regular, non-hardlinked notes are editable")
                if hasattr(os, "geteuid") and info.st_uid != os.geteuid():
                    raise FileAccessError("The note must be owned by the current user")
                return file.read(), info
        except EditError:
            raise
        except OSError as exc:
            raise FileAccessError("Unable to read the source note") from exc

    def _prepare(self, handle: EditHandle, action: str, due_date: str | None,
                 title: str | None = None, fields: dict | None = None) -> tuple[Path, _Prepared]:
        path = self._path(handle)
        data, info = self._read(path)
        if hashlib.sha256(data).hexdigest() != handle.digest:
            raise StaleSnapshot("Source note changed; refresh and retry")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeError as exc:
            raise UnsupportedTask("Note is not valid UTF-8") from exc
        project = handle.source.split("/", 1)[0]
        parsed, issues = parse_markdown(text, handle.source, project)
        if any(issue.message.startswith("unclosed") for issue in issues):
            raise UnsupportedTask("Malformed Markdown region; edit in Obsidian")
        task = next((item for item in parsed if item.line == handle.line), None)
        if task is None or task.original != handle.original:
            raise StaleSnapshot("Target task moved or changed; refresh")
        if any(issue.line == handle.line for issue in issues):
            raise UnsupportedTask("Malformed task metadata; edit in Obsidian")

        raw_lines = data.splitlines(keepends=True)
        raw_line = raw_lines[handle.line - 1]
        bom = b"\xef\xbb\xbf" if handle.line == 1 and raw_line.startswith(b"\xef\xbb\xbf") else b""
        line_bytes = raw_line[len(bom):]
        newline = b"\r\n" if line_bytes.endswith(b"\r\n") else b"\n" if line_bytes.endswith(b"\n") else b"\r" if line_bytes.endswith(b"\r") else b""
        before = line_bytes[:len(line_bytes) - len(newline)].decode("utf-8")
        if before != handle.original:
            raise StaleSnapshot("Target line changed; refresh")
        if action == "fields":
            if not isinstance(fields, dict):
                raise InvalidEdit("Invalid edit form")
            current_fields = self.fields_for(before)
            if fields.get("depends_on") != current_fields["depends_on"]:
                self._validate_dependencies(fields.get("depends_on"), before)
            after = self._transform_fields(before, fields)
        else:
            after = self._transform(before, task, action, due_date, title)
        if after == before:
            raise InvalidEdit("No change to apply")
        raw_lines[handle.line - 1] = bom + after.encode("utf-8") + newline
        updated = b"".join(raw_lines)
        updated_tasks, updated_issues = parse_markdown(updated.decode("utf-8-sig"), handle.source, project)
        modified = next((item for item in updated_tasks if item.line == handle.line), None)
        if modified is None or modified.original != after or any(issue.line == handle.line for issue in updated_issues):
            raise UnsupportedTask("Proposed edit does not parse as a valid task")
        if action == "title" and (modified.due != task.due or modified.recurrence != task.recurrence
                                  or modified.tags != task.tags or modified.completed != task.completed):
            raise UnsupportedTask("Task metadata would change; edit the title in Obsidian")
        if action == "fields" and self.fields_for(after) != fields:
            raise UnsupportedTask("Proposed task metadata is ambiguous; edit in Obsidian")
        return path, _Prepared(EditPreview(before, after, handle.source, handle.line), data, updated,
                               info.st_dev, info.st_ino, stat.S_IMODE(info.st_mode))

    @staticmethod
    def title_parts(before: str) -> tuple[str, str, str]:
        marker = TASK.match(before)
        if marker is None:
            raise UnsupportedTask("Unsupported checkbox")
        prefix = before[:marker.start(2)]
        rest = before[marker.start(2):]
        # Tasks plugin examples often put #task before the description.
        leading_tags = re.match(r"(?:#[\w/-]+[ \t]+)+", rest)
        if leading_tags:
            prefix += leading_tags.group()
            rest = rest[leading_tags.end():]
        metadata = TITLE_METADATA.search(rest)
        end = metadata.start() if metadata else len(rest)
        current_title = rest[:end].rstrip(" \t")
        if not current_title:
            raise UnsupportedTask("Task has no editable title; use Obsidian")
        suffix = rest[len(current_title):]
        remaining = suffix
        for pattern in (
            r"(?<!\S)(?:📅|⏳|🛫|➕|✅|❌)[ \t]+\S+",
            r"(?<!\S)(?:🔺|⏫|🔼|🔽|⏬)(?=\s|$)",
            RECURRENCE_FIELD,
            DEPENDENCY_FIELD, ID_FIELD,
            r"(?<!\S)🏁[ \t]+(?:keep|delete)(?=\s|$)",
            TAG_TOKEN,
            r"(?<!\S)\^[A-Za-z0-9-]+(?=\s|$)",
        ):
            remaining = re.sub(pattern, "", remaining)
        if remaining.strip():
            raise UnsupportedTask("Text after task metadata is ambiguous; edit in Obsidian")
        return prefix, current_title, suffix

    @staticmethod
    def fields_for(before: str) -> dict[str, str]:
        marker = TASK.match(before)
        if marker is None:
            raise UnsupportedTask("Unsupported checkbox status")
        title = TaskWriter.title_parts(before)[1]
        fields = {"title": title, "status": {" ": "todo", "x": "done", "-": "cancelled"}[marker.group(1).lower()]}
        for name, symbol in DATE_MARKERS.items():
            occurrences = list(re.finditer(rf"(?<!\S){re.escape(symbol)}(?=\s|$)", before))
            if len(occurrences) > 1:
                raise UnsupportedTask(f"Multiple {name} markers; edit in Obsidian")
            if occurrences:
                found = re.search(rf"(?<!\S){re.escape(symbol)}[ \t]+(\S+)", before)
                if not found or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", found.group(1)):
                    raise UnsupportedTask(f"Malformed {name} date; edit in Obsidian")
                try:
                    date.fromisoformat(found.group(1))
                except ValueError as exc:
                    raise UnsupportedTask(f"Malformed {name} date; edit in Obsidian") from exc
                fields[name] = found.group(1)
            else:
                fields[name] = ""
        found_priorities = [(name, match) for name, symbol in PRIORITIES.items() if symbol
                            for match in re.finditer(rf"(?<!\S){re.escape(symbol)}(?=\s|$)", before)]
        if len(found_priorities) > 1:
            raise UnsupportedTask("Multiple priority markers; edit in Obsidian")
        fields["priority"] = found_priorities[0][0] if found_priorities else "normal"
        occurrences = list(re.finditer(r"(?<!\S)🔁(?=\s|$)", before))
        if len(occurrences) > 1:
            raise UnsupportedTask("Multiple recurrence markers; edit in Obsidian")
        recurrence = RECURRENCE_FIELD.search(before)
        if occurrences and not recurrence:
            raise UnsupportedTask("Malformed recurrence; edit in Obsidian")
        fields["recurrence"] = recurrence.group(1).strip() if recurrence else ""
        for name, symbol, pattern in (("depends_on", "⛔", DEPENDENCY_FIELD), ("id", "🆔", ID_FIELD)):
            occurrences = list(re.finditer(rf"(?<!\S){symbol}(?=\s|$)", before))
            if len(occurrences) > 1 or (occurrences and not pattern.search(before)):
                raise UnsupportedTask(f"Ambiguous {name} field; edit in Obsidian")
            found = pattern.search(before)
            fields[name] = found.group(1) if found else ""
        tokens = list(TAG_TOKEN.finditer(marker.group(2)))
        if tuple(match.group()[1:] for match in tokens) != tuple(TAG.findall(marker.group(2))):
            raise UnsupportedTask("Ambiguous tags; edit in Obsidian")
        fields["tags"] = " ".join(match.group() for match in tokens)
        return fields

    def _validate_dependencies(self, value: object, before: str) -> None:
        if not isinstance(value, str) or (value and not re.fullmatch(
                r"[A-Za-z0-9_-]+(?:,[ \t]*[A-Za-z0-9_-]+)*", value)):
            raise InvalidEdit("Enter comma-separated existing task IDs")
        ids = [item.strip() for item in value.split(",") if item.strip()]
        if len(ids) != len(set(ids)):
            raise InvalidEdit("Duplicate dependency ID")
        own = self.fields_for(before)["id"]
        if own and own in ids:
            raise InvalidEdit("A task cannot depend on itself")
        seen: dict[str, int] = {}
        graph: dict[str, list[str]] = {}
        for task in scan(self.root, tuple(self.excludes)).tasks:
            found = ID_FIELD.search(task.original)
            if found:
                task_id = found.group(1)
                seen[task_id] = seen.get(task_id, 0) + 1
                dependency = DEPENDENCY_FIELD.search(task.original)
                graph[task_id] = ([item.strip() for item in dependency.group(1).split(",")]
                                  if dependency else [])
        if any(seen.get(item) != 1 for item in ids):
            raise UnsupportedTask("Each dependency ID must identify exactly one task in this Projects directory")
        if own:
            for dependency in ids:
                pending = [dependency]
                visited: set[str] = set()
                while pending:
                    item = pending.pop()
                    if item == own:
                        raise InvalidEdit("Dependency would create a cycle")
                    if item not in visited:
                        visited.add(item)
                        pending.extend(graph.get(item, []))

    @staticmethod
    def _set_field(line: str, name: str, old: str, new: str, symbol: str, pattern: re.Pattern) -> str:
        if old == new:
            return line
        found = pattern.search(line)
        if old and not found:
            raise UnsupportedTask(f"Could not locate {name} marker")
        if found:
            if new:
                return line[:found.start(1)] + new + line[found.end(1):]
            start = found.start() - 1 if found.start() and line[found.start() - 1] in " \t" else found.start()
            return line[:start] + line[found.end():]
        block = TRAILING_BLOCK.search(line)
        pos = block.start() if block else len(line.rstrip(" \t"))
        return line[:pos] + f" {symbol}" + (f" {new}" if new else "") + line[pos:]

    @staticmethod
    def _transform_fields(before: str, fields: dict) -> str:
        old = TaskWriter.fields_for(before)
        if set(fields) != set(old) or any(not isinstance(value, str) for value in fields.values()) or fields["id"] != old["id"]:
            raise InvalidEdit("Invalid or unsupported task fields")
        if fields["status"] not in ("todo", "done", "cancelled") or fields["priority"] not in PRIORITIES:
            raise InvalidEdit("Choose a supported status and priority")
        if fields["title"] != old["title"]:
            before = TaskWriter._transform(before, Task("", "", 0, "", before, False, None, None, None, ()),
                                           "title", None, fields["title"])
        if fields["status"] != old["status"]:
            if old["recurrence"] and fields["status"] != "todo":
                raise UnsupportedTask("Recurring tasks cannot be completed or cancelled in MarkTask yet")
            marker = TASK.match(before)
            assert marker is not None
            start, end = marker.span(1)
            before = before[:start] + {"todo": " ", "done": "x", "cancelled": "-"}[fields["status"]] + before[end:]
        for name, symbol in DATE_MARKERS.items():
            value = fields[name]
            if value:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    raise InvalidEdit(f"Enter {name} as YYYY-MM-DD")
                try:
                    date.fromisoformat(value)
                except ValueError as exc:
                    raise InvalidEdit(f"Invalid {name} date") from exc
            pattern = re.compile(rf"(?<!\S){re.escape(symbol)}[ \t]+(\S+)")
            before = TaskWriter._set_field(before, name, old[name], value, symbol, pattern)
        if fields["priority"] != old["priority"]:
            pattern = re.compile(r"(?<!\S)(🔺|⏫|🔼|🔽|⏬)(?=\s|$)")
            found = pattern.search(before)
            symbol = PRIORITIES[fields["priority"]]
            if found:
                if symbol:
                    before = before[:found.start()] + symbol + before[found.end():]
                else:
                    start = found.start() - 1 if found.start() and before[found.start() - 1] in " \t" else found.start()
                    before = before[:start] + before[found.end():]
            elif symbol:
                block = TRAILING_BLOCK.search(before)
                pos = block.start() if block else len(before.rstrip(" \t"))
                before = before[:pos] + " " + symbol + before[pos:]
        if fields["recurrence"] != old["recurrence"]:
            value = fields["recurrence"]
            if value and (not RECURRENCE_RULE.fullmatch(value) or not any(fields[k] for k in ("due", "scheduled", "start"))):
                raise InvalidEdit("Use a supported 'every ...' rule with a due, scheduled or start date")
            before = TaskWriter._set_field(before, "recurrence", old["recurrence"], value, "🔁", RECURRENCE_FIELD)
        if fields["depends_on"] != old["depends_on"]:
            before = TaskWriter._set_field(before, "depends_on", old["depends_on"], fields["depends_on"],
                                           "⛔", DEPENDENCY_FIELD)
        if fields["tags"] != old["tags"]:
            values = fields["tags"].split()
            if any(not re.fullmatch(r"#[\w/-]+", tag) for tag in values) or len(values) != len(set(values)):
                raise InvalidEdit("Use unique space-separated #tags")
            before = re.sub(r"[ \t]+#[\w/-]+(?=\s|$)", "", before)
            block = TRAILING_BLOCK.search(before)
            pos = block.start() if block else len(before.rstrip(" \t"))
            if values:
                before = before[:pos] + " " + " ".join(values) + before[pos:]
        return before

    @staticmethod
    def _transform(before: str, task: Task, action: str, due_date: str | None,
                   title: str | None = None) -> str:
        if action == "toggle":
            if "🔁" in task.text:
                raise UnsupportedTask("Recurring tasks cannot be completed or reopened yet")
            marker = TASK.match(before)
            if marker is None:
                raise UnsupportedTask("Unsupported checkbox")
            start, end = marker.span(1)
            return before[:start] + (" " if task.completed or task.cancelled else "x") + before[end:]
        if action == "title":
            if (not isinstance(title, str) or not title.strip() or title != title.strip()
                    or "\n" in title or "\r" in title or any(token in title for token in ("📅", "✅", "🔁"))
                    or re.search(r"(?<!\S)(?:#[\w/-]+|\^[A-Za-z0-9-]+)(?=\s|$)", title)):
                raise InvalidEdit("Enter a non-empty title without task metadata or line breaks")
            prefix, _old_title, suffix = TaskWriter.title_parts(before)
            return prefix + title + suffix
        if action != "due":
            raise InvalidEdit("Unknown edit action")
        if due_date is not None:
            if not isinstance(due_date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due_date):
                raise InvalidEdit("Enter a valid date in YYYY-MM-DD format")
            try:
                date.fromisoformat(due_date)
            except ValueError as exc:
                raise InvalidEdit("Enter a valid calendar date") from exc
        if before.count("📅") > 1:
            raise UnsupportedTask("Multiple due dates; edit in Obsidian")
        marker = DUE.search(before)
        if "📅" in before and (marker is None or task.due is None):
            raise UnsupportedTask("Malformed due date; edit in Obsidian")
        if marker is not None:
            start, end = marker.span(1)
            if due_date is not None:
                return before[:start] + due_date + before[end:]
            prefix = before[:marker.start()].rstrip(" \t")
            return prefix + before[marker.end():]
        if due_date is None:
            raise InvalidEdit("Task has no due date to remove")
        block = TRAILING_BLOCK.search(before)
        if block:
            return before[:block.start()].rstrip(" \t") + f" 📅 {due_date}" + before[block.start():]
        return before.rstrip(" \t") + f" 📅 {due_date}" + before[len(before.rstrip(" \t")):]

    def preview(self, handle: EditHandle, action: str, due_date: str | None = None,
                 title: str | None = None, fields: dict | None = None) -> EditPreview:
        return self._prepare(handle, action, due_date, title, fields)[1].preview

    @staticmethod
    def _move_tag(before: str, destination: str, lanes: tuple[str, ...]) -> str:
        known = {lane_slug(name) for name in lanes}
        tokens = [match for match in re.finditer(r"(?<!\S)#todo(?:/[\w-]+)?(?=\s|$)", before)
                  if match.group() == "#todo" or match.group()[6:].casefold() in known]
        if len(tokens) > 1:
            raise UnsupportedTask("Multiple workflow tags; resolve them in Obsidian before moving")
        if tokens:
            match = tokens[0]
            if match.end() < len(before) and before[match.end()] in " \t":
                before = before[:match.start()] + before[match.end() + 1:]
            else:
                start = match.start() - 1 if match.start() and before[match.start() - 1] in " \t" else match.start()
                before = before[:start] + before[match.end():]
        tag = "#todo" if destination == "Backlog" else f"#todo/{lane_slug(destination)}"
        block = TRAILING_BLOCK.search(before)
        position = block.start() if block else len(before.rstrip(" \t"))
        return before[:position] + " " + tag + before[position:]

    def _prepare_move(self, handle: EditHandle, destination: str,
                      fields: dict | None = None) -> tuple[Path, _Prepared]:
        if not isinstance(destination, str):
            raise InvalidEdit("Choose a Kanban lane")
        path = self._path(handle)
        data, info = self._read(path)
        if hashlib.sha256(data).hexdigest() != handle.digest:
            raise StaleSnapshot("Source note changed; refresh and retry")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeError as exc:
            raise UnsupportedTask("Note is not valid UTF-8") from exc
        index = scan(self.root, tuple(self.excludes))
        task = next((item for item in index.tasks if item.source == handle.source and item.line == handle.line
                     and item.original == handle.original and item.file_digest == handle.digest), None)
        if task is None:
            raise StaleSnapshot("Target task moved or changed; refresh")
        if task.parent_line is not None:
            raise UnsupportedTask("Nested subtasks stay with their parent; move the parent task instead")
        if task.is_board and task.board_source != handle.source:
            raise UnsupportedTask("This board has no matching project master note; move in Obsidian")
        lanes = index.lanes.get(task.project, ())
        targets = lanes if task.is_board else tuple(dict.fromkeys(("Backlog", *(lanes or task.lanes))))
        if destination not in targets or (task.is_board and task.column == destination):
            raise InvalidEdit("Choose a different lane in this project's board")
        if task_column(task) == destination:
            raise InvalidEdit("Task is already in that lane")
        parsed, issues = parse_markdown(text, handle.source, task.project)
        if any(issue.message.startswith("unclosed") or issue.line == handle.line for issue in issues):
            raise UnsupportedTask("Malformed Markdown region; move in Obsidian")
        if not any(item.line == handle.line and item.original == handle.original for item in parsed):
            raise StaleSnapshot("Target task moved or changed; refresh")
        lines = data.splitlines(keepends=True)
        before_line = lines[handle.line - 1].decode("utf-8-sig").rstrip("\r\n")
        if before_line != handle.original:
            raise StaleSnapshot("Target line changed; refresh")
        changed_line = before_line if fields is None else self._transform_fields(before_line, fields)
        if fields is not None and self.fields_for(changed_line) != fields:
            raise UnsupportedTask("Proposed task metadata is ambiguous; edit in Obsidian")
        changed_task = parse_markdown(changed_line, handle.source, task.project)[0]
        if not changed_task or changed_task[0].completed or changed_task[0].cancelled:
            raise UnsupportedTask("Reopen the task before moving it; moves do not change completion")
        newline = b"\r\n" if lines[handle.line - 1].endswith(b"\r\n") else (
            b"\n" if lines[handle.line - 1].endswith(b"\n") else b"\r" if lines[handle.line - 1].endswith(b"\r") else b"")

        if task.is_board:
            sections = board_sections(text)
            if sections is None or tuple(name for name, _ in sections) != lanes:
                raise UnsupportedTask("Board headings are ambiguous; move in Obsidian")
            start = handle.line - 1
            if before_line[0].isspace():
                raise UnsupportedTask("Nested board tasks move with their parent card")
            source_heading = next((name for name, position in reversed(sections) if position < start), None)
            if source_heading != task.column:
                raise UnsupportedTask("Could not identify the source board lane")
            boundary = next((position for _name, position in sections if position > start), len(lines))
            end = start + 1
            while end < boundary:
                content = lines[end].decode("utf-8").rstrip("\r\n")
                if not content.strip():
                    end += 1
                elif content[0] in " \t":
                    end += 1
                elif content.startswith("%% kanban:settings"):
                    break
                elif re.match(r"[-*+]\s", content):
                    break
                else:
                    raise UnsupportedTask("Unclear board card boundary; move in Obsidian")
            if end == len(lines) and lines[end - 1] and not lines[end - 1].endswith((b"\n", b"\r")):
                raise UnsupportedTask("Board card has no terminating newline; move in Obsidian")
            block = [changed_line.encode("utf-8") + newline, *lines[start + 1:end]]
            remaining = lines[:start] + lines[end:]
            updated_sections = board_sections(b"".join(remaining).decode("utf-8-sig"))
            assert updated_sections is not None
            target_heading = next(position for name, position in updated_sections if name == destination)
            insert = target_heading + 1
            if not remaining[target_heading].endswith((b"\n", b"\r")):
                raise UnsupportedTask("Destination heading has no terminating newline")
            while insert < len(remaining) and not remaining[insert].strip():
                insert += 1
            updated = b"".join(remaining[:insert] + block + remaining[insert:])
            moved, new_issues = parse_markdown(updated.decode("utf-8-sig"), handle.source, task.project)
            if (len(moved) != len(parsed) or any(issue.message.startswith("unclosed") for issue in new_issues)
                    or not any(item.line == insert + 1 and item.original == changed_line
                               and item.column == destination for item in moved)):
                raise UnsupportedTask("Proposed board move does not preserve the task")
            card_before = b"".join(lines[start:end]).decode("utf-8").rstrip("\r\n")
            card_after = b"".join(block).decode("utf-8").rstrip("\r\n")
            preview = EditPreview(f"## {source_heading}\n{card_before}", f"## {destination}\n{card_after}",
                                  handle.source, handle.line)
        else:
            after = self._move_tag(changed_line, destination, task.lanes)
            if after == before_line:
                raise InvalidEdit("No change to apply")
            lines[handle.line - 1] = after.encode("utf-8") + newline
            updated = b"".join(lines)
            moved, new_issues = parse_markdown(updated.decode("utf-8-sig"), handle.source, task.project)
            changed = next((item for item in moved if item.line == handle.line), None)
            if (changed is None or changed.original != after or any(issue.line == handle.line for issue in new_issues)
                    or task_column(replace(changed, lanes=task.lanes)) != destination):
                raise UnsupportedTask("Proposed workflow tag does not assign the requested lane")
            preview = EditPreview(before_line, after, handle.source, handle.line)
        return path, _Prepared(preview, data, updated, info.st_dev, info.st_ino, stat.S_IMODE(info.st_mode))

    def preview_move(self, handle: EditHandle, destination: str) -> EditPreview:
        return self._prepare_move(handle, destination)[1].preview

    def preview_change(self, handle: EditHandle, fields: dict, destination: str) -> EditPreview:
        task = self._scanned_task(handle)
        if destination == task_column(task):
            preview = self.preview(handle, "fields", fields=fields)
            self._validate_change_lane(handle, preview.after, destination, task)
            return preview
        return self._prepare_move(handle, destination, fields)[1].preview

    def _scanned_task(self, handle: EditHandle) -> Task:
        task = next((item for item in scan(self.root, tuple(self.excludes)).tasks
                     if item.source == handle.source and item.line == handle.line
                     and item.original == handle.original and item.file_digest == handle.digest), None)
        if task is None:
            raise StaleSnapshot("Task changed; refresh and retry")
        return task

    @staticmethod
    def _validate_change_lane(handle: EditHandle, after: str, destination: str, task: Task) -> None:
        parsed, _ = parse_markdown(after, handle.source, task.project)
        if not parsed:
            raise InvalidEdit("Proposed task is not a valid checkbox")
        if parsed[0].completed or parsed[0].cancelled or task.completed or task.cancelled:
            return  # Status is explicitly edited; it takes precedence over the lane.
        if task_column(replace(parsed[0], lanes=task.lanes, column=task.column,
                                board_source=task.board_source, parent_lane=task.parent_lane)) != destination:
            raise InvalidEdit("Workflow tags would change the selected lane; use the Lane field")

    def apply_change(self, handle: EditHandle, fields: dict, destination: str,
                     expected_after: str) -> EditPreview:
        path = self._path(handle)
        with _lock_for(path):
            task = self._scanned_task(handle)
            if destination == task_column(task):
                path, prepared = self._prepare(handle, "fields", None, fields=fields)
                self._validate_change_lane(handle, prepared.preview.after, destination, task)
            else:
                path, prepared = self._prepare_move(handle, destination, fields)
            if expected_after != prepared.preview.after:
                raise StaleSnapshot("Edit preview changed; review again")
            self._commit(path, handle, prepared)
            return prepared.preview

    def _prepare_create_lane(self, project: str, name: str,
                             expected_digest: str | None = None) -> tuple[Path, _Prepared]:
        if (not isinstance(name, str) or not 1 <= len(name) <= 64 or name != name.strip()
                or not re.fullmatch(r"[\w][\w -]*", name) or not lane_slug(name)):
            raise InvalidEdit("Use a short lane name of letters, numbers, spaces, hyphens or underscores")
        index = scan(self.root, tuple(self.excludes))
        if not isinstance(project, str) or project not in index.boards:
            raise UnsupportedTask("Create lanes only in projects with a paired _Kanban note")
        source = index.boards[project]
        path = self._path(EditHandle(source, 1, "", expected_digest or ""))
        data, info = self._read(path)
        digest = hashlib.sha256(data).hexdigest()
        if expected_digest is not None and digest != expected_digest:
            raise StaleSnapshot("Kanban note changed; refresh and retry")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeError as exc:
            raise UnsupportedTask("Kanban note is not valid UTF-8") from exc
        sections = board_sections(text)
        if sections is None or tuple(lane for lane, _ in sections) != index.lanes[project]:
            raise UnsupportedTask("Board headings changed; refresh")
        if lane_slug(name) in {lane_slug(lane) for lane, _ in sections}:
            raise InvalidEdit("A lane with that name already exists")
        lines = data.splitlines(keepends=True)
        insert = next((i for i, line in enumerate(lines)
                       if line.lstrip().startswith(b"%% kanban:settings")), len(lines))
        if not lines or (insert and not lines[insert - 1].endswith((b"\n", b"\r"))):
            raise UnsupportedTask("Board note needs a final newline before adding a lane")
        newline = b"\r\n" if any(line.endswith(b"\r\n") for line in lines) else b"\n"
        addition = f"## {name}".encode("utf-8") + newline + newline
        updated = b"".join(lines[:insert] + [addition] + lines[insert:])
        new_sections = board_sections(updated.decode("utf-8-sig"))
        if (new_sections is None or len(new_sections) != len(sections) + 1
                or new_sections[len(sections)][0] != name):
            raise UnsupportedTask("Proposed lane does not parse as a Kanban heading")
        preview = EditPreview("(no lane with this name)", f"## {name}", source, insert + 1)
        return path, _Prepared(preview, data, updated, info.st_dev, info.st_ino, stat.S_IMODE(info.st_mode))

    def preview_create_lane(self, project: str, name: str) -> tuple[EditPreview, str]:
        _path, prepared = self._prepare_create_lane(project, name)
        return prepared.preview, hashlib.sha256(prepared.original_bytes).hexdigest()

    def apply_create_lane(self, project: str, name: str, expected_digest: str,
                          expected_after: str) -> EditPreview:
        index = scan(self.root, tuple(self.excludes))
        if not isinstance(project, str) or project not in index.boards:
            raise UnsupportedTask("Project board is no longer available; refresh")
        source = index.boards[project]
        handle = EditHandle(source, 1, "", expected_digest)
        path = self._path(handle)
        with _lock_for(path):
            path, prepared = self._prepare_create_lane(project, name, expected_digest)
            if expected_after != prepared.preview.after:
                raise StaleSnapshot("Lane preview changed; review again")
            self._commit(path, handle, prepared)
            return prepared.preview

    def apply_move(self, handle: EditHandle, destination: str, expected_after: str) -> EditPreview:
        path = self._path(handle)
        with _lock_for(path):
            path, prepared = self._prepare_move(handle, destination)
            if expected_after != prepared.preview.after:
                raise StaleSnapshot("Move preview changed; review again")
            self._commit(path, handle, prepared)
            return prepared.preview

    def apply(self, handle: EditHandle, action: str, due_date: str | None = None,
              expected_after: str | None = None, title: str | None = None,
              fields: dict | None = None) -> EditPreview:
        path = self._path(handle)
        with _lock_for(path):
            path, prepared = self._prepare(handle, action, due_date, title, fields)
            if expected_after is not None and expected_after != prepared.preview.after:
                raise StaleSnapshot("Edit preview changed; review again")
            self._commit(path, handle, prepared)
            return prepared.preview

    def _commit(self, path: Path, handle: EditHandle, prepared: _Prepared) -> None:
        temp_path: str | None = None
        replaced = False
        try:
            fd, temp_path = tempfile.mkstemp(prefix=".marktask-", suffix=".tmp", dir=path.parent)
            with os.fdopen(fd, "wb") as temporary:
                os.fchmod(temporary.fileno(), prepared.mode)
                temporary.write(prepared.updated_bytes)
                temporary.flush()
                os.fsync(temporary.fileno())
            self._path(handle)  # Refuse a parent/leaf that became a symlink while preparing.
            current, info = self._read(path)
            if (current != prepared.original_bytes or info.st_dev != prepared.device
                    or info.st_ino != prepared.inode):
                raise StaleSnapshot("Source note changed during editing; refresh")
            os.replace(temp_path, path)
            replaced = True
            temp_path = None
            if hasattr(os, "O_DIRECTORY"):
                directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        except EditError:
            raise
        except OSError as exc:
            if replaced:
                raise UncertainWrite("The note was replaced, but directory sync failed; inspect it in Obsidian") from exc
            raise FileAccessError("Unable to finish writing the note; inspect it before retrying") from exc
        finally:
            if temp_path is not None:
                try:
                    os.unlink(temp_path)
                except FileNotFoundError:
                    pass
