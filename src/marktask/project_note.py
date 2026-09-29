"""Read a selected project's master note without modifying vault files."""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass
from datetime import date, datetime
from html import escape
from pathlib import Path, PurePosixPath
from typing import Callable

import yaml


MAX_NOTE_BYTES = 1_000_000
MARKDOWN_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]+\)|!\[([^\]]*)\]\[[^\]]*\]|!\[\[([^\]]+)\]\]")
WIKILINK = re.compile(r"(?<!!)\[\[([^\]\n]+)\]\]")
CALLOUT = re.compile(r"^\s*>\s*\[!([\w-]+)\]([ \t]*.*)$", re.IGNORECASE)


@dataclass(frozen=True)
class ProjectNote:
    source: str | None
    properties: tuple[tuple[str, str], ...] = ()
    body: str = ""
    message: str | None = None
    raw_properties: str | None = None


def _display(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ", ".join(_display(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def _safe_markdown(content: str) -> str:
    """Avoid automatic network fetches from image syntax in a local-only dashboard."""
    return MARKDOWN_IMAGE.sub(lambda match: f"[Image or attachment: {next((g for g in match.groups() if g), 'unnamed')}]", content)


def preview_markdown(body: str, link_for: Callable[[str], str | None] | None = None) -> str:
    """Render a small Obsidian subset; escape all source HTML before adding trusted links.

    Unknown callout types retain their label; wikilinks show their display name
    without inventing an ambiguous or potentially remote destination.
    """
    output: list[str] = []
    fence = ""

    def wikilink(match: re.Match) -> str:
        raw = match.group(1)
        target, separator, alias = raw.partition("|")
        display = alias if separator else target.split("#", 1)[0] or target
        if link_for is None:
            return display
        uri = link_for(target.strip())
        if uri is None:
            return (f'<span class="unresolved-wikilink" title="Not uniquely found in Projects">'
                    f'{escape(display)}</span>')
        return (f'<a href="{escape(uri, quote=True)}" target="_blank" '
                f'rel="noopener noreferrer">{escape(display)}</a>')

    def linkify(line: str) -> str:
        parts: list[str] = []
        start = 0
        for match in WIKILINK.finditer(line):
            parts.extend((escape(line[start:match.start()]), wikilink(match)))
            start = match.end()
        parts.append(escape(line[start:]))
        return "".join(parts)

    for line in body.splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if not fence:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = ""
        if not fence and not marker:
            callout = CALLOUT.match(line)
            if callout:
                kind, title = callout.groups()
                line = f"> **{kind.replace('-', ' ').title()}**{title}"
            if link_for is not None:
                # Retain Markdown's quote marker while escaping any raw HTML in its text.
                quote = re.match(r"^\s*(?:>\s*)+", line)
                prefix = quote.group() if quote else ""
                rest = line[len(prefix):]
                line = prefix + (escape(rest) if "`" in rest else linkify(rest))
            else:
                line = WIKILINK.sub(wikilink, line)
            # Markdown joins consecutive plain lines. Keep Obsidian-style line breaks
            # for properties/text, but let list, quote and heading blocks parse normally.
            if (output and output[-1].strip() and line.strip()
                    and not re.match(r"\s*(?:[-*+]\s|\d+\.\s|>|#|---+$|`{3,}|~{3,})", line)
                    and not re.match(r"\s*(?:[-*+]\s|\d+\.\s|>|#|---+$|`{3,}|~{3,})", output[-1])):
                output[-1] += "  "
        elif link_for is not None:
            line = escape(line)
        output.append(line)
    return "\n".join(output)


def load_project_note(projects_dir: Path, project: str) -> ProjectNote:
    """Only direct, non-symlinked _*.md notes in the selected project are candidates."""
    relative = PurePosixPath(project)
    if (not project or relative.is_absolute() or "\\" in project
            or any(part in ("", ".", "..") for part in project.split("/"))):
        return ProjectNote(None, message="No project master note for this folder.")
    folder = projects_dir
    for part in relative.parts:
        folder = folder / part
        if folder.is_symlink() or not folder.is_dir():
            return ProjectNote(None, message="No project master note for this folder.")
    try:
        candidates = sorted(
            path for path in folder.iterdir()
            if path.is_file() and not path.is_symlink() and path.suffix.lower() == ".md"
            and path.name.startswith("_") and not path.stem.casefold().startswith("_kanban")
        )
    except OSError:
        return ProjectNote(None, message="Could not inspect project notes.")
    exact = next((path for path in candidates if path.stem == "_" + relative.name), None)
    if exact is not None:
        path = exact
    elif len(candidates) == 1:
        path = candidates[0]
    elif candidates:
        return ProjectNote(None, message="Several _*.md notes could be the master note; none was selected automatically.")
    else:
        return ProjectNote(None, message="No project master note found (_ProjectName.md).")

    source = path.relative_to(projects_dir).as_posix()
    try:
        descriptor_read = (hasattr(os, "O_DIRECTORY") and hasattr(os, "O_NOFOLLOW")
                           and os.open in getattr(os, "supports_dir_fd", ()))
        folder_fd = None
        try:
            if descriptor_read:
                folder_fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                file_fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=folder_fd)
            else:
                before = path.lstat()
                if folder.is_symlink() or not stat.S_ISREG(before.st_mode):
                    return ProjectNote(source, message="Master note is not a regular file.")
                file_fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(file_fd, "rb") as file:
                info = os.fstat(file.fileno())
                if not stat.S_ISREG(info.st_mode):
                    return ProjectNote(source, message="Master note is not a regular file.")
                if not descriptor_read and (folder.is_symlink() or not os.path.samestat(info, before)
                                            or not os.path.samestat(info, path.lstat())):
                    return ProjectNote(source, message="Master note changed while opening it.")
                if info.st_size > MAX_NOTE_BYTES:
                    return ProjectNote(source, message="Master note is too large for an inline preview; open it in Obsidian.")
                data = file.read(MAX_NOTE_BYTES + 1)
        finally:
            if folder_fd is not None:
                os.close(folder_fd)
        if len(data) > MAX_NOTE_BYTES:
            return ProjectNote(source, message="Master note is too large for an inline preview; open it in Obsidian.")
        text = data.decode("utf-8-sig")
    except (OSError, UnicodeError):
        return ProjectNote(source, message="Could not read the master note as UTF-8.")

    lines = text.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        end = next((i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---"), None)
        if end is None:
            return ProjectNote(source, body=_safe_markdown(text), message="Unclosed properties block; showing note as written.")
        raw = "".join(lines[1:end])
        body = "".join(lines[end + 1:])
        try:
            parsed = yaml.safe_load(raw)
            if parsed is None:
                return ProjectNote(source, body=_safe_markdown(body))
            if not isinstance(parsed, dict):
                raise ValueError("Properties must be a mapping")
            return ProjectNote(source, tuple((str(key), _display(value)) for key, value in parsed.items()),
                               _safe_markdown(body))
        except (yaml.YAMLError, ValueError):
            return ProjectNote(source, body=_safe_markdown(body), raw_properties=raw,
                               message="Could not parse properties; showing them as text.")
    return ProjectNote(source, body=_safe_markdown(text))
