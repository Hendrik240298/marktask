"""CLI for explicit Projects-directory scans and a localhost-only dashboard."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from marktask.index import DEFAULT_EXCLUDES, scan, visible_tasks
from marktask.links import ObsidianLinks, find_vault_root


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Markdown project task index and dashboard")
    parser.add_argument("command", nargs="?", choices=("scan", "serve"), default="serve")
    parser.add_argument("--projects-dir", type=Path, required=True, help="Direct path to a Projects directory")
    parser.add_argument("--exclude", action="append", default=[], metavar="NAME", help="Additional directory or file name to skip (repeatable)")
    parser.add_argument("--visibility-file", type=Path, help="Visibility rules JSON (default: .marktask-visibility.json in Projects directory)")
    parser.add_argument("--port", type=int, default=8050, help="Local dashboard port (default: 8050)")
    parser.add_argument("--allow-writes", action="store_true", help="Enable guarded single-task editing in the dashboard (off by default)")
    parser.add_argument("--advanced-uri", action="store_true", help="Use optional Obsidian Advanced URI plugin to open exact task lines")
    parser.add_argument("--obsidian-vault-root", type=Path, help="Vault root for exact-line or block links (auto-detected from .obsidian otherwise)")
    parser.add_argument("--obsidian-vault", help="Obsidian vault name or ID (defaults to vault folder name)")
    args = parser.parse_args()
    if not args.projects_dir.is_dir():
        parser.error("--projects-dir must name an existing directory")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if args.command == "scan" and args.allow_writes:
        parser.error("--allow-writes applies only to the dashboard")
    excludes = (*DEFAULT_EXCLUDES, *args.exclude)

    if args.command == "scan":
        index = scan(args.projects_dir, excludes)
        today = date.today()
        print(f"Projects: {len(index.projects)} | Files: {index.files} | Tasks: {len(index.tasks)} | Warnings: {len(index.warnings)}")
        for view in ("today", "overdue", "upcoming", "waiting"):
            print(f"{view.title()}: {len(visible_tasks(index.tasks, view, today))}")
        for issue in index.warnings:
            location = f"{issue.source}:{issue.line}" if issue.line is not None else issue.source
            print(f"WARN {location}: {issue.message}")
    else:
        from marktask.dashboard import create_app

        vault_root = args.obsidian_vault_root or find_vault_root(args.projects_dir)
        try:
            links = ObsidianLinks(args.projects_dir, vault_root, args.obsidian_vault, args.advanced_uri)
        except ValueError as exc:
            parser.error(str(exc))
        app = create_app(args.projects_dir, excludes, links=links, allow_writes=args.allow_writes,
                         visibility_file=args.visibility_file)
        app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
