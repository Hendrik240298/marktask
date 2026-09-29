from datetime import date
from pathlib import Path

import pytest

from marktask.index import ROOT_PROJECT, parse_markdown, scan, task_column, visible_tasks


def test_board_parser_preserves_context_and_ignores_non_tasks():
    content = """---
kanban-plugin: board
---
## Waiting
- [ ] Prüfen [[Note]] 📅 2026-09-30 🔁 every week #work ^abc
  - [X] Subtask ✅ 2026-09-27
```markdown
- [ ] example 📅 2026-09-28
```
%% kanban:settings
- [ ] hidden
%%
## Done
- [x] Finished
"""
    tasks, warnings = parse_markdown(content, "Example/Kanban.md", "Example")
    assert not warnings
    assert len(tasks) == 3
    assert (tasks[0].column, tasks[0].due, tasks[0].recurrence, tasks[0].line) == (
        "Waiting", date(2026, 9, 30), "every week #work ^abc", 5,
    )
    assert tasks[0].tags == ("work",)
    assert tasks[1].completed and tasks[1].column == "Waiting"
    assert tasks[2].column == "Done"


def test_plain_notes_do_not_infer_kanban_status_and_report_bad_dates():
    tasks, warnings = parse_markdown("## Waiting\n- [ ] Item 📅 2026-02-30\n- [ ] Item", "A/a.md", "A")
    assert len(tasks) == 2  # duplicate-looking tasks are separate locations
    assert all(task.column is None for task in tasks)
    assert tasks[0].due is None
    assert (warnings[0].source, warnings[0].line, warnings[0].message) == (
        "A/a.md", 2, "invalid due date",
    )


def test_unclosed_frontmatter_skips_file_safely():
    tasks, warnings = parse_markdown("---\n- [ ] Task", "bad.md", ROOT_PROJECT)
    assert not tasks
    assert warnings[0].message == "unclosed frontmatter; file skipped"


def test_code_fences_do_not_close_on_inline_backticks_and_wikilinks_are_not_tags():
    tasks, warnings = parse_markdown(
        "```markdown\n```python\n- [ ] example\n```\n- [ ] [[Note#Section]] #actual\n",
        "A.md", ROOT_PROJECT,
    )
    assert not warnings
    assert len(tasks) == 1
    assert tasks[0].tags == ("actual",)


def test_scan_scopes_tree_and_handles_nested_loose_empty_and_symlinks(tmp_path: Path):
    root = tmp_path / "1-Projects"
    root.mkdir()
    (root / "empty").mkdir()
    nested = root / "Work" / "Meeting"
    nested.mkdir(parents=True)
    (nested / "notes.md").write_text("- [ ] Meeting action\n", encoding="utf-8")
    (root / "loose.md").write_text("- [ ] Loose\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("- [ ] Outside\n", encoding="utf-8")
    (root / "external").symlink_to(outside, target_is_directory=True)
    (root / "linked.md").symlink_to(outside / "secret.md")
    (root / "skip").mkdir()
    (root / "skip" / "ignored.md").write_text("- [ ] Ignore\n", encoding="utf-8")
    index = scan(root, excludes=("skip",))
    assert index.projects == (ROOT_PROJECT, "Work", "empty")
    assert index.files == 2
    assert {(t.project, t.source) for t in index.tasks} == {
        ("Work", "Work/Meeting/notes.md"), (ROOT_PROJECT, "loose.md"),
    }


def test_malformed_file_does_not_stop_scan(tmp_path: Path):
    (tmp_path / "broken.md").write_bytes(b"\xff")
    (tmp_path / "good.md").write_text("- [ ] Fine\n", encoding="utf-8")
    index = scan(tmp_path)
    assert len(index.tasks) == 1
    assert index.warnings[0].source == "broken.md"


def test_date_views_are_disjoint_and_completed_tasks_do_not_appear():
    text = "\n".join([
        "- [ ] Old 📅 2026-09-27", "- [ ] Today 📅 2026-09-28",
        "- [ ] Soon 📅 2026-09-29", "- [x] Done 📅 2026-09-28",
        "- [ ] Late 📅 2026-10-06",
    ])
    tasks, _ = parse_markdown(text, "A.md", ROOT_PROJECT)
    today = date(2026, 9, 28)
    assert [t.text.split()[0] for t in visible_tasks(tuple(tasks), "overdue", today)] == ["Old"]
    assert [t.text.split()[0] for t in visible_tasks(tuple(tasks), "today", today)] == ["Today"]
    assert [t.text.split()[0] for t in visible_tasks(tuple(tasks), "upcoming", today)] == ["Soon"]


def test_invalid_path_is_not_silently_replaced_by_sample(tmp_path: Path):
    with pytest.raises(ValueError, match="does not exist"):
        scan(tmp_path / "missing")


def test_board_assignment_prefers_completion_native_column_then_workflow_tag():
    notes, _ = parse_markdown("\n".join([
        "- [ ] Untagged", "- [ ] Reference #research", "- [ ] Ready #todo/privat #next/privat",
        "- [ ] In flight #doing", "- [ ] Paused #waiting", "- [x] Completed #next", "- [ ] Capture #inbox/privat",
    ]), "Team/notes.md", "Team")
    board, _ = parse_markdown("---\nkanban-plugin: board\n---\n## Doing - Hendrik\n- [ ] Native #next\n",
                              "Team/Kanban.md", "Team")
    assert [task_column(task) for task in notes + board] == [
        "Backlog", "Backlog", "Next", "In Progress", "Waiting", "Done", "Inbox", "Doing - Hendrik",
    ]
    assert len(visible_tasks(tuple(notes + board), "waiting", date.today())) == 1
    assert len(visible_tasks(tuple(notes + board), "inbox", date.today())) == 1


def test_nested_master_creates_project_and_orphan_board_is_not_parent_board(tmp_path: Path):
    parent = tmp_path / "Parent"
    child = parent / "Child"
    orphan = parent / "Orphan"
    child.mkdir(parents=True)
    orphan.mkdir()
    (parent / "_Parent.md").write_text("- [ ] Parent item\n", encoding="utf-8")
    (child / "_Child.md").write_text("- [ ] Child item\n", encoding="utf-8")
    (child / "_Kanban Child.md").write_text(
        "---\nkanban-plugin: board\n---\n## Next\n\n## Doing - Hendrik\n- [ ] Board item\n",
        encoding="utf-8",
    )
    (orphan / "_Kanban Orphan.md").write_text(
        "---\nkanban-plugin: board\n---\n## Waiting\n- [ ] Orphan item\n", encoding="utf-8",
    )
    index = scan(tmp_path)
    assert index.projects == ("Parent", "Parent/Child")
    assert index.boards == {"Parent/Child": "Parent/Child/_Kanban Child.md"}
    assert index.lanes["Parent/Child"] == ("Next", "Doing - Hendrik")
    assert {task.text: task.project for task in index.tasks} == {
        "Parent item": "Parent", "Child item": "Parent/Child", "Board item": "Parent/Child",
        "Orphan item": "Parent",
    }
    assert task_column(next(task for task in index.tasks if task.text == "Orphan item")) == "Backlog"
    assert any("not paired" in issue.message for issue in index.warnings)


def test_only_matching_todo_lanes_count_and_bare_todo_is_backlog(tmp_path: Path):
    project = tmp_path / "Work"
    project.mkdir()
    (project / "_Work.md").write_text("# Work\n", encoding="utf-8")
    (project / "_Kanban Work.md").write_text(
        "---\nkanban-plugin: board\n---\n## To Do\n\n## Doing - Hendrik\n\n## Done\n",
        encoding="utf-8",
    )
    (project / "notes.md").write_text(
        "- [ ] Context #todo/privat\n- [ ] Base #todo\n"
        "- [ ] Assigned #todo/doing-hendrik #todo/privat\n", encoding="utf-8",
    )
    index = scan(tmp_path)
    assert [task_column(task) for task in index.tasks] == ["Backlog", "Backlog", "Doing - Hendrik"]
