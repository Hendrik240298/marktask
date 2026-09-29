"""Build read-only Obsidian links from source locations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from marktask.index import Task


BLOCK_ID = re.compile(r"(?:^|\s)\^([A-Za-z0-9-]+)\s*$")


def find_vault_root(projects_dir: Path) -> Path | None:
    """Find a containing vault by its standard .obsidian folder, if present."""
    path = projects_dir.absolute()
    for parent in (path, *path.parents):
        if (parent / ".obsidian").is_dir():
            return parent
    return None


@dataclass(frozen=True)
class ObsidianLinks:
    projects_dir: Path
    vault_root: Path | None = None
    vault_name: str | None = None
    advanced_uri: bool = False

    def __post_init__(self) -> None:
        if self.advanced_uri and self.vault_root is None:
            raise ValueError("Exact-line links need an Obsidian vault root")
        if self.vault_root is not None:
            try:
                self.projects_dir.absolute().relative_to(self.vault_root.absolute())
            except ValueError as exc:
                raise ValueError("Obsidian vault root must contain the Projects directory") from exc

    def for_task(self, task: Task) -> tuple[str, str]:
        """Return URI and honest tooltip: exact line, block, or file only."""
        path = (self.projects_dir.absolute() / task.source)
        encoded_path = quote(str(path), safe="")
        if self.vault_root is not None:
            relative = path.relative_to(self.vault_root.absolute()).as_posix()
            vault = quote(self.vault_name or self.vault_root.name, safe="")
            if self.advanced_uri:
                return (
                    f"obsidian://adv-uri?vault={vault}&filepath={quote(relative, safe='')}&line={task.line}",
                    f"Open in Obsidian at line {task.line} (Advanced URI plugin)",
                )
            block = BLOCK_ID.search(task.original)
            if block:
                target = quote(f"{relative}#^{block.group(1)}", safe="")
                return (f"obsidian://open?vault={vault}&file={target}",
                        "Open this task block in Obsidian")
        return (f"obsidian://open?path={encoded_path}",
                 f"Open note in Obsidian; line {task.line} is shown for manual navigation")

    def for_note(self, source: str) -> str:
        """Open a project note as a file, with no invented task-line location."""
        path = self.projects_dir.absolute() / source
        if self.vault_root is not None:
            relative = path.relative_to(self.vault_root.absolute()).as_posix()
            vault = quote(self.vault_name or self.vault_root.name, safe="")
            return f"obsidian://open?vault={vault}&file={quote(relative, safe='')}"
        return f"obsidian://open?path={quote(str(path), safe='')}"

    def for_wikilink(self, target: str, source: str, sources: tuple[str, ...]) -> str | None:
        """Link only to an unambiguous Markdown file in the selected Projects tree."""
        name = target.split("#", 1)[0].strip()
        if not name:  # [[#Heading]] refers to this note.
            return self.for_note(source) if source in sources else None
        if (name.startswith("/") or "\\" in name or ":" in name
                or any(part in ("", ".", "..") for part in name.split("/"))):
            return None
        if name.casefold().endswith(".md"):
            name = name[:-3]
        prefix = self.projects_dir.name + "/"
        if name.casefold().startswith(prefix.casefold()):
            name = name[len(prefix):]
        if not name:
            return None
        parent = PurePosixPath(source).parent
        candidates = [item for item in sources if item.casefold().endswith(".md")
                      and (item[:-3].casefold() == name.casefold()
                           or item[:-3].casefold().endswith("/" + name.casefold()))]
        local = (parent / f"{name}.md").as_posix()
        direct = [item for item in candidates if item.casefold() == local.casefold()]
        if len(direct) == 1:
            return self.for_note(direct[0])
        return self.for_note(candidates[0]) if len(candidates) == 1 else None
