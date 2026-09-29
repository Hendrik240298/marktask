"""Local dashboard visibility rules; never alter or exclude Markdown source files."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from marktask.index import Task


class VisibilityError(ValueError):
    pass


DEFAULT_REFERENCE_GLOBS = ("templates",)


@dataclass(frozen=True)
class VisibilityRules:
    reference_globs: tuple[str, ...] = DEFAULT_REFERENCE_GLOBS
    task_globs: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, list[str]]:
        return {"reference_globs": list(self.reference_globs), "task_globs": list(self.task_globs)}


def validate_pattern(pattern: str) -> str:
    anchored = isinstance(pattern, str) and pattern.startswith("./")
    value = pattern[2:] if anchored else pattern
    if (not isinstance(pattern, str) or not pattern or pattern != pattern.strip()
            or len(pattern) > 512 or value.startswith("/") or "\\" in pattern
            or any(part in ("", ".", "..") for part in value.split("/"))
            or any(char in pattern for char in "\r\n\0")):
        raise VisibilityError("Use a file or folder name, or a relative path glob (up to 512 characters)")
    return pattern


def file_rule_from_input(value: str, projects_dir: Path) -> str:
    """Accept a pasted absolute path without persisting a machine-specific location."""
    if not isinstance(value, str):
        raise VisibilityError("Enter a file or folder path")
    value = value.strip()
    if value.startswith("file://"):
        uri = urlsplit(value)
        if uri.netloc not in ("", "localhost") or uri.query or uri.fragment:
            raise VisibilityError("Use a local file path inside the selected Projects directory")
        value = unquote(uri.path)
    if not value.startswith("/"):
        return validate_pattern(value)
    path = Path(value)
    if ".." in path.parts:
        raise VisibilityError("Paths containing .. are not supported")
    try:
        relative = path.relative_to(projects_dir.absolute())
    except ValueError as exc:
        raise VisibilityError("Path must be inside the selected Projects directory") from exc
    if not relative.parts:
        raise VisibilityError("Choose a file or folder inside Projects, not Projects itself")
    current = projects_dir
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise VisibilityError("Symlinked paths are not indexed; choose a regular file or folder")
    exact = "".join({"*": "[*]", "?": "[?]", "[": "[[]"}.get(char, char)
                    for char in relative.as_posix())
    if current.is_dir():
        return validate_pattern("./" + exact + "/*")
    if current.is_file() and current.suffix.casefold() == ".md":
        return validate_pattern("./" + exact)
    raise VisibilityError("Choose an existing Markdown file or folder inside Projects")


def validate_task_pattern(pattern: str) -> str:
    if (not isinstance(pattern, str) or not pattern or pattern != pattern.strip()
            or len(pattern) > 200 or any(char in pattern for char in "\r\n\0")):
        raise VisibilityError("Use task text, or File/path.md :: task text (up to 200 characters)")
    source, separator, text = pattern.partition("::")
    if separator and (not text.strip() or not source.strip()):
        raise VisibilityError("Enter both a source glob and task text around ::")
    if separator:
        validate_pattern(source.strip())
    return pattern


def matches(source: str, pattern: str) -> bool:
    """Single names match any file/folder component; paths match from the root."""
    if pattern.startswith("./"):
        return fnmatch.fnmatchcase(source, pattern[2:])
    if "/" in pattern:
        return fnmatch.fnmatchcase(source, pattern)
    return any(fnmatch.fnmatchcase(part, pattern) for part in PurePosixPath(source).parts)


def is_reference(source: str, patterns: tuple[str, ...]) -> bool:
    return any(matches(source, pattern) for pattern in patterns)


def is_reference_task(task: Task, rules: VisibilityRules) -> bool:
    if is_reference(task.source, rules.reference_globs):
        return True
    for pattern in rules.task_globs:
        source, separator, text = pattern.partition("::")
        if separator and not matches(task.source, source.strip()):
            continue
        term = (text if separator else source).strip().casefold()
        value = task.text.casefold()
        matched = (fnmatch.fnmatchcase(value, term) if any(char in term for char in "*?[")
                   else term in value)
        if matched:
            return True
    return False


def _parse_rules(value: object) -> VisibilityRules:
    if not isinstance(value, dict) or not {"reference_globs"} <= value.keys() or set(value) - {
            "reference_globs", "task_globs"}:
        raise ValueError("Invalid visibility keys")
    files = value["reference_globs"]
    tasks = value.get("task_globs", [])
    if (not isinstance(files, list) or not isinstance(tasks, list)
            or any(not isinstance(item, str) for item in [*files, *tasks])
            or len(files) != len(set(files)) or len(tasks) != len(set(tasks))):
        raise ValueError("Invalid rule list")
    return VisibilityRules(tuple(validate_pattern(item) for item in files),
                           tuple(validate_task_pattern(item) for item in tasks))


def load_rules(path: Path) -> tuple[VisibilityRules, str]:
    """Return rules and an exact snapshot of the config (including a missing file)."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return VisibilityRules(), "missing"
    except OSError as exc:
        raise VisibilityError("Visibility file must be a readable, regular (non-symlink) file") from exc
    try:
        with os.fdopen(fd, "rb") as file:
            if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
                raise VisibilityError("Visibility file must be a regular file")
            data = file.read(16_385)
        if len(data) > 16_384:
            raise VisibilityError("Visibility file must be a small JSON file")
    except OSError as exc:
        raise VisibilityError("Could not read visibility file") from exc
    try:
        return _parse_rules(json.loads(data)), hashlib.sha256(data).hexdigest()
    except (UnicodeError, ValueError, TypeError, KeyError) as exc:
        raise VisibilityError("Invalid visibility file; fix the JSON before continuing") from exc


def save_rules(path: Path, patterns: VisibilityRules, digest: str) -> None:
    """Atomically replace a reviewed configuration only if its snapshot still matches."""
    patterns = _parse_rules(patterns.as_dict())
    current, snapshot = load_rules(path)
    if snapshot != digest:
        raise VisibilityError("Visibility rules changed; review again")
    if patterns == current:
        raise VisibilityError("No visibility change to save")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise VisibilityError("Visibility file directory is unavailable")
    data = (json.dumps(patterns.as_dict(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".marktask-", delete=False) as file:
            temporary = Path(file.name)
            os.fchmod(file.fileno(), 0o600)
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        if load_rules(path)[1] != digest:
            raise VisibilityError("Visibility rules changed; review again")
        os.replace(temporary, path)
    except OSError as exc:
        raise VisibilityError("Could not save visibility rules") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
