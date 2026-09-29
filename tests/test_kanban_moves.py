from pathlib import Path

import pytest

from marktask.index import scan, task_column
from marktask.writer import EditHandle, InvalidEdit, StaleSnapshot, TaskWriter, UnsupportedTask


def selected(root: Path, source: str, line: int) -> EditHandle:
    return EditHandle.from_task(next(task for task in scan(root).tasks if task.source == source and task.line == line))


def project(tmp_path: Path) -> Path:
    folder = tmp_path / "Work"
    folder.mkdir()
    (folder / "_Work.md").write_text("# Work\n", encoding="utf-8")
    (folder / "_Kanban Work.md").write_text(
        "---\nkanban-plugin: board\n---\n## Backlog\n\n## Doing - Hendrik\n\n## Done\n",
        encoding="utf-8",
    )
    return folder


def test_tag_move_keeps_note_and_context_tags(tmp_path: Path):
    folder = project(tmp_path)
    note = folder / "notes.md"
    original = b"Intro\r\n- [ ] Plan #todo/privat #todo ^task\r\n  - [ ] Child\r\nAfter\n"
    note.write_bytes(original)
    writer = TaskWriter(tmp_path)
    handle = selected(tmp_path, "Work/notes.md", 2)
    preview = writer.preview_move(handle, "Doing - Hendrik")
    assert preview.after == "- [ ] Plan #todo/privat #todo/doing-hendrik ^task"
    assert note.read_bytes() == original
    writer.apply_move(handle, "Doing - Hendrik", preview.after)
    assert note.read_bytes() == original.replace(b"#todo ^task", b"#todo/doing-hendrik ^task")
    assert task_column(next(t for t in scan(tmp_path).tasks if t.line == 2 and t.source == "Work/notes.md")) == "Doing - Hendrik"
    assert (folder / "_Kanban Work.md").read_text().endswith("## Done\n")
    handle = selected(tmp_path, "Work/notes.md", 2)
    writer.apply_move(handle, "Backlog", writer.preview_move(handle, "Backlog").after)
    assert note.read_bytes() == original


def test_board_move_preserves_child_lines_other_cards_and_mixed_endings(tmp_path: Path):
    folder = project(tmp_path)
    board = folder / "_Kanban Work.md"
    original = ("---\r\nkanban-plugin: board\r\n---\r\n## Backlog\r\n"
                "- [ ] Parent ^abc\r\n  - [ ] Child 📅 2026-10-01\r\n"
                "  More card context\r\n- [ ] Sibling\r\n## Doing - Hendrik\r\n"
                "- [ ] Existing\r\n## Done\r\n%% kanban:settings\nsettings\n%%\n").encode("utf-8")
    board.write_bytes(original)
    writer = TaskWriter(tmp_path)
    handle = selected(tmp_path, "Work/_Kanban Work.md", 5)
    preview = writer.preview_move(handle, "Doing - Hendrik")
    assert "Child" in preview.before and "Child" in preview.after
    assert board.read_bytes() == original
    writer.apply_move(handle, "Doing - Hendrik", preview.after)
    expected = ("---\r\nkanban-plugin: board\r\n---\r\n## Backlog\r\n"
                "- [ ] Sibling\r\n## Doing - Hendrik\r\n"
                "- [ ] Parent ^abc\r\n  - [ ] Child 📅 2026-10-01\r\n"
                "  More card context\r\n- [ ] Existing\r\n## Done\r\n%% kanban:settings\nsettings\n%%\n").encode("utf-8")
    assert board.read_bytes() == expected
    assert [task_column(t) for t in scan(tmp_path).tasks if t.source.endswith("_Kanban Work.md")] == [
        "Backlog", "Doing - Hendrik", "Doing - Hendrik", "Doing - Hendrik",
    ]


def test_move_rejects_stale_snapshot_without_writing(tmp_path: Path):
    folder = project(tmp_path)
    note = folder / "notes.md"
    note.write_text("- [ ] Task #todo\n", encoding="utf-8")
    writer = TaskWriter(tmp_path)
    handle = selected(tmp_path, "Work/notes.md", 1)
    preview = writer.preview_move(handle, "Doing - Hendrik")
    note.write_text("- [ ] Task #todo\nExternal change\n", encoding="utf-8")
    with pytest.raises(StaleSnapshot):
        writer.apply_move(handle, "Doing - Hendrik", preview.after)
    assert note.read_text().endswith("External change\n")


def test_moves_fail_closed_for_orphan_board_completed_or_ambiguous_tag(tmp_path: Path):
    folder = project(tmp_path)
    writer = TaskWriter(tmp_path)
    note = folder / "notes.md"
    note.write_text("- [x] Finished\n- [ ] Doubled #todo #todo/doing-hendrik\n", encoding="utf-8")
    with pytest.raises(UnsupportedTask, match="Reopen"):
        writer.preview_move(selected(tmp_path, "Work/notes.md", 1), "Backlog")
    with pytest.raises(UnsupportedTask, match="Multiple workflow"):
        writer.preview_move(selected(tmp_path, "Work/notes.md", 2), "Backlog")
    orphan = folder / "Sub"
    orphan.mkdir()
    (orphan / "_Kanban Sub.md").write_text(
        "---\nkanban-plugin: board\n---\n## Backlog\n- [ ] Orphan\n", encoding="utf-8",
    )
    with pytest.raises(UnsupportedTask, match="no matching project master"):
        writer.preview_move(selected(tmp_path, "Work/Sub/_Kanban Sub.md", 5), "Backlog")


def test_board_child_cannot_move_alone_and_unknown_target_cannot_write(tmp_path: Path):
    folder = project(tmp_path)
    board = folder / "_Kanban Work.md"
    board.write_text("---\nkanban-plugin: board\n---\n## Backlog\n- [ ] Parent\n  - [ ] Child\n## Done\n",
                     encoding="utf-8")
    writer = TaskWriter(tmp_path)
    with pytest.raises(UnsupportedTask, match="Nested"):
        writer.preview_move(selected(tmp_path, "Work/_Kanban Work.md", 6), "Done")
    with pytest.raises(InvalidEdit):
        writer.apply_move(selected(tmp_path, "Work/_Kanban Work.md", 5), "Not a lane", "forged")
    assert board.read_text().splitlines()[4] == "- [ ] Parent"


def test_board_card_abutting_settings_and_ambiguous_continuation(tmp_path: Path):
    folder = project(tmp_path)
    board = folder / "_Kanban Work.md"
    board.write_text(
        "---\nkanban-plugin: board\n---\n## Backlog\n- [ ] First\n"
        "## Doing - Hendrik\n- [ ] Last\n%% kanban:settings\nfoo\n%%\n", encoding="utf-8",
    )
    writer = TaskWriter(tmp_path)
    last = selected(tmp_path, "Work/_Kanban Work.md", 7)
    writer.apply_move(last, "Backlog", writer.preview_move(last, "Backlog").after)
    assert "## Backlog\n- [ ] Last\n- [ ] First\n" in board.read_text()
    assert board.read_text().endswith("%% kanban:settings\nfoo\n%%\n")
    board.write_text(
        "---\nkanban-plugin: board\n---\n## Backlog\n- [ ] Card\n"
        "Unindented prose of uncertain ownership\n## Doing - Hendrik\n", encoding="utf-8",
    )
    with pytest.raises(UnsupportedTask, match="boundary"):
        writer.preview_move(selected(tmp_path, "Work/_Kanban Work.md", 5), "Doing - Hendrik")


def test_combined_form_and_lane_change_is_one_guarded_write(tmp_path: Path):
    folder = project(tmp_path)
    note = folder / "notes.md"
    note.write_bytes(b"- [ ] Original #todo ^id\r\nUnrelated\n")
    writer = TaskWriter(tmp_path)
    handle = selected(tmp_path, "Work/notes.md", 1)
    fields = writer.fields_for(handle.original)
    fields.update(title="Updated", priority="high")
    preview = writer.preview_change(handle, fields, "Doing - Hendrik")
    assert preview.after == "- [ ] Updated ⏫ #todo/doing-hendrik ^id"
    assert note.read_bytes().startswith(b"- [ ] Original")
    writer.apply_change(handle, fields, "Doing - Hendrik", preview.after)
    assert note.read_bytes() == (preview.after + "\r\nUnrelated\n").encode("utf-8")


def test_combined_board_card_edit_and_move_keeps_child_lines(tmp_path: Path):
    folder = project(tmp_path)
    board = folder / "_Kanban Work.md"
    board.write_text(
        "---\nkanban-plugin: board\n---\n## Backlog\n- [ ] Parent\n  - [ ] Child\n"
        "## Doing - Hendrik\n", encoding="utf-8",
    )
    writer = TaskWriter(tmp_path)
    handle = selected(tmp_path, "Work/_Kanban Work.md", 5)
    fields = writer.fields_for(handle.original)
    fields.update(title="Updated parent", due="2026-10-11")
    preview = writer.preview_change(handle, fields, "Doing - Hendrik")
    assert "## Backlog\n- [ ] Parent\n  - [ ] Child" == preview.before
    assert "## Doing - Hendrik\n- [ ] Updated parent 📅 2026-10-11\n  - [ ] Child" == preview.after
    writer.apply_change(handle, fields, "Doing - Hendrik", preview.after)
    assert "## Doing - Hendrik\n- [ ] Updated parent 📅 2026-10-11\n  - [ ] Child" in board.read_text()


def test_form_cannot_change_workflow_tag_without_lane_choice(tmp_path: Path):
    folder = project(tmp_path)
    note = folder / "notes.md"
    note.write_text("- [ ] Task #todo\n", encoding="utf-8")
    writer = TaskWriter(tmp_path)
    handle = selected(tmp_path, "Work/notes.md", 1)
    fields = writer.fields_for(handle.original)
    fields["tags"] = "#todo/doing-hendrik"
    with pytest.raises(InvalidEdit, match="Lane field"):
        writer.preview_change(handle, fields, "Backlog")
    assert note.read_text() == "- [ ] Task #todo\n"


def test_create_lane_adds_heading_to_paired_board_after_review(tmp_path: Path):
    folder = project(tmp_path)
    board = folder / "_Kanban Work.md"
    before = board.read_bytes() + b"%% kanban:settings\n{}\n%%\n"
    board.write_bytes(before)
    writer = TaskWriter(tmp_path)
    preview, digest = writer.preview_create_lane("Work", "Review - Team")
    assert preview.after == "## Review - Team"
    assert board.read_bytes() == before
    writer.apply_create_lane("Work", "Review - Team", digest, preview.after)
    assert board.read_bytes() == before.replace(
        b"%% kanban:settings", b"## Review - Team\n\n%% kanban:settings", 1,
    )
    assert scan(tmp_path).lanes["Work"][-1] == "Review - Team"
    with pytest.raises(InvalidEdit, match="already exists"):
        writer.preview_create_lane("Work", "review-team")


def test_lane_creation_rejects_unpaired_board_invalid_names_and_stale_snapshot(tmp_path: Path):
    folder = project(tmp_path)
    writer = TaskWriter(tmp_path)
    board = folder / "_Kanban Work.md"
    original = board.read_bytes()
    for name in ("", " Leading", "Bad\n## Inject", "Name #tag"):
        with pytest.raises(InvalidEdit):
            writer.preview_create_lane("Work", name)
    preview, digest = writer.preview_create_lane("Work", "Review")
    board.write_bytes(original + b"External\n")
    with pytest.raises(StaleSnapshot):
        writer.apply_create_lane("Work", "Review", digest, preview.after)
    assert board.read_bytes().endswith(b"External\n")
    unpaired = tmp_path / "No board"
    unpaired.mkdir()
    (unpaired / "_No board.md").write_text("# No board\n", encoding="utf-8")
    with pytest.raises(UnsupportedTask, match="paired"):
        writer.preview_create_lane("No board", "Review")
