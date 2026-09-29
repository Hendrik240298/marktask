import os
import stat
from datetime import date
from pathlib import Path

import pytest

from marktask.index import scan, visible_tasks
from marktask.writer import (
    EditHandle, FileAccessError, InvalidEdit, StaleSnapshot, TaskWriter, UncertainWrite, UnsupportedTask,
)


def handle(root: Path, source: str, line: int = 1) -> EditHandle:
    task = next(task for task in scan(root).tasks if task.source == source and task.line == line)
    return EditHandle.from_task(task)


def test_preview_is_read_only_and_toggle_preserves_every_other_byte(tmp_path: Path):
    note = tmp_path / "notes.md"
    original = b"\xef\xbb\xbfintro\r\n  - [ ] Pr\xc3\xbcfen #tag ^abc\n- [ ] other\r\n"
    note.write_bytes(original)
    note.chmod(0o640)
    writer = TaskWriter(tmp_path)
    selected = handle(tmp_path, "notes.md", 2)
    preview = writer.preview(selected, "toggle")
    assert preview.before == "  - [ ] Prüfen #tag ^abc"
    assert preview.after == "  - [x] Prüfen #tag ^abc"
    assert note.read_bytes() == original
    writer.apply(selected, "toggle", expected_after=preview.after)
    assert note.read_bytes() == original.replace(b"  - [ ]", b"  - [x]", 1)
    assert stat.S_IMODE(note.stat().st_mode) == 0o640
    with pytest.raises(StaleSnapshot):
        writer.apply(selected, "toggle")
    reopened = handle(tmp_path, "notes.md", 2)
    writer.apply(reopened, "toggle")
    assert note.read_bytes() == original


def test_identical_task_lines_remain_distinct_by_line_number(tmp_path: Path):
    note = tmp_path / "tasks.md"
    note.write_text("- [ ] Same\n- [ ] Same\n", encoding="utf-8")
    TaskWriter(tmp_path).apply(handle(tmp_path, "tasks.md", 2), "toggle")
    assert note.read_text() == "- [ ] Same\n- [x] Same\n"


def test_first_line_utf8_bom_and_no_final_newline_survive(tmp_path: Path):
    note = tmp_path / "tasks.md"
    original = b"\xef\xbb\xbf- [ ] Task"
    note.write_bytes(original)
    TaskWriter(tmp_path).apply(handle(tmp_path, "tasks.md"), "toggle")
    assert note.read_bytes() == b"\xef\xbb\xbf- [x] Task"


def test_external_changes_including_unrelated_lines_are_conflicts(tmp_path: Path):
    note = tmp_path / "tasks.md"
    note.write_text("- [ ] Task\nOther\n", encoding="utf-8")
    selected = handle(tmp_path, "tasks.md")
    note.write_text("- [ ] Task\nChanged elsewhere\n", encoding="utf-8")
    with pytest.raises(StaleSnapshot):
        TaskWriter(tmp_path).apply(selected, "toggle")
    assert note.read_text() == "- [ ] Task\nChanged elsewhere\n"


def test_due_date_add_replace_remove_and_views(tmp_path: Path):
    note = tmp_path / "Task.md"
    note.write_text("- [ ] Review #next ^id123\r\n", encoding="utf-8", newline="")
    writer = TaskWriter(tmp_path)
    writer.apply(handle(tmp_path, "Task.md"), "due", "2026-09-29")
    assert note.read_bytes() == b"- [ ] Review #next \xf0\x9f\x93\x85 2026-09-29 ^id123\r\n"
    assert len(visible_tasks(scan(tmp_path).tasks, "upcoming", date(2026, 9, 28))) == 1
    writer.apply(handle(tmp_path, "Task.md"), "due", "2026-09-28")
    assert len(visible_tasks(scan(tmp_path).tasks, "today", date(2026, 9, 28))) == 1
    writer.apply(handle(tmp_path, "Task.md"), "due")
    assert note.read_bytes() == b"- [ ] Review #next ^id123\r\n"


@pytest.mark.parametrize("bad_date", ["2026-02-30", "yesterday", "2026-1-01"])
def test_invalid_dates_do_not_write(tmp_path: Path, bad_date: str):
    note = tmp_path / "tasks.md"
    note.write_text("- [ ] Task\n", encoding="utf-8")
    with pytest.raises(InvalidEdit):
        TaskWriter(tmp_path).apply(handle(tmp_path, "tasks.md"), "due", bad_date)
    assert note.read_text() == "- [ ] Task\n"


def test_title_change_only_replaces_wording_and_preserves_task_metadata(tmp_path: Path):
    note = tmp_path / "tasks.md"
    original = ("- [ ] Old title #next 📅 2026-09-30 🔁 every week ^abc\r\n"
                "- [x] Finished ✅ 2026-09-28\r\n").encode("utf-8")
    note.write_bytes(original)
    writer = TaskWriter(tmp_path)
    selected = handle(tmp_path, "tasks.md")
    assert writer.title_parts(selected.original)[1] == "Old title"
    preview = writer.preview(selected, "title", title="New **title**")
    assert note.read_bytes() == original
    assert preview.after == "- [ ] New **title** #next 📅 2026-09-30 🔁 every week ^abc"
    writer.apply(selected, "title", expected_after=preview.after, title="New **title**")
    assert note.read_bytes() == original.replace(b"Old title", b"New **title**")
    with pytest.raises(StaleSnapshot):
        writer.apply(selected, "title", title="Again")


@pytest.mark.parametrize("bad_title", ["", " ", " Leading space", "Bad\nline", "New 📅 2026-10-01", "New #tag", "New ^block"])
def test_invalid_title_is_refused_without_writing(tmp_path: Path, bad_title: str):
    note = tmp_path / "tasks.md"
    original = "- [ ] Original #work 📅 2026-09-30 ^abc\n"
    note.write_text(original, encoding="utf-8")
    with pytest.raises(InvalidEdit):
        TaskWriter(tmp_path).apply(handle(tmp_path, "tasks.md"), "title", title=bad_title)
    assert note.read_text(encoding="utf-8") == original


def test_title_with_no_wording_is_refused(tmp_path: Path):
    note = tmp_path / "tasks.md"
    note.write_text("- [ ] #inbox 📅 2026-09-30\n", encoding="utf-8")
    with pytest.raises(UnsupportedTask):
        TaskWriter(tmp_path).apply(handle(tmp_path, "tasks.md"), "title", title="New title")


def test_ambiguous_and_malformed_due_dates_are_not_editable(tmp_path: Path):
    note = tmp_path / "tasks.md"
    note.write_text("- [ ] Task 📅 2026-10-01 📅 2026-11-01\n", encoding="utf-8")
    with pytest.raises(UnsupportedTask):
        TaskWriter(tmp_path).apply(handle(tmp_path, "tasks.md"), "due", "2026-12-01")
    note.write_text("- [ ] Task 📅 2026-02-30\n", encoding="utf-8")
    with pytest.raises(UnsupportedTask):
        TaskWriter(tmp_path).apply(handle(tmp_path, "tasks.md"), "due", "2026-12-01")


def test_recurring_task_cannot_be_completed(tmp_path: Path):
    note = tmp_path / "tasks.md"
    note.write_text("- [ ] Weekly 🔁 every week\n", encoding="utf-8")
    with pytest.raises(UnsupportedTask, match="Recurring"):
        TaskWriter(tmp_path).apply(handle(tmp_path, "tasks.md"), "toggle")
    assert note.read_text() == "- [ ] Weekly 🔁 every week\n"


def test_excluded_paths_traversal_and_symlinks_are_refused(tmp_path: Path):
    note = tmp_path / "tasks.md"
    note.write_text("- [ ] Task\n", encoding="utf-8")
    selected = handle(tmp_path, "tasks.md")
    writer = TaskWriter(tmp_path)
    for source in ("../tasks.md", "/tmp/tasks.md", "tasks.md/../tasks.md", "attachments/private.md"):
        with pytest.raises(InvalidEdit):
            writer.preview(EditHandle(source, 1, selected.original, selected.digest), "toggle")
    (tmp_path / "alias.md").symlink_to(note)
    with pytest.raises(InvalidEdit):
        writer.preview(EditHandle("alias.md", 1, selected.original, selected.digest), "toggle")
    (tmp_path / "alias-dir").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(InvalidEdit):
        writer.preview(EditHandle("alias-dir/tasks.md", 1, selected.original, selected.digest), "toggle")


def test_malformed_region_and_hardlinked_files_are_refused(tmp_path: Path):
    note = tmp_path / "tasks.md"
    note.write_text("- [ ] Real\n```\n- [ ] example\n", encoding="utf-8")
    with pytest.raises(UnsupportedTask):
        TaskWriter(tmp_path).apply(handle(tmp_path, "tasks.md"), "toggle")
    note.write_text("- [ ] Real\n", encoding="utf-8")
    os.link(note, tmp_path / "linked.md")
    with pytest.raises(UnsupportedTask):
        TaskWriter(tmp_path).apply(handle(tmp_path, "tasks.md"), "toggle")


def test_failure_before_atomic_replace_preserves_original_and_cleans_temp(tmp_path: Path, monkeypatch):
    note = tmp_path / "tasks.md"
    note.write_text("- [ ] Task\n", encoding="utf-8")

    def fail_replace(*args):
        raise OSError("simulated failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(FileAccessError):
        TaskWriter(tmp_path).apply(handle(tmp_path, "tasks.md"), "toggle")
    assert note.read_text() == "- [ ] Task\n"
    assert [p.name for p in tmp_path.iterdir()] == ["tasks.md"]


def test_change_during_write_is_caught_at_final_recheck(tmp_path: Path, monkeypatch):
    note = tmp_path / "tasks.md"
    note.write_text("- [ ] Task\n", encoding="utf-8")
    selected = handle(tmp_path, "tasks.md")
    read = TaskWriter._read
    calls = 0

    def external_change(path):
        nonlocal calls
        calls += 1
        if calls == 2:
            note.write_text("- [ ] Task\nNew note context\n", encoding="utf-8")
        return read(path)

    monkeypatch.setattr(TaskWriter, "_read", staticmethod(external_change))
    with pytest.raises(StaleSnapshot, match="during editing"):
        TaskWriter(tmp_path).apply(selected, "toggle")
    assert note.read_text() == "- [ ] Task\nNew note context\n"
    assert [p.name for p in tmp_path.iterdir()] == ["tasks.md"]


def test_directory_sync_failure_is_not_reported_as_no_change(tmp_path: Path, monkeypatch):
    note = tmp_path / "tasks.md"
    note.write_text("- [ ] Task\n", encoding="utf-8")
    fsync = os.fsync
    calls = 0

    def fail_directory_sync(fd):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated directory sync failure")
        return fsync(fd)

    monkeypatch.setattr(os, "fsync", fail_directory_sync)
    with pytest.raises(UncertainWrite, match="was replaced"):
        TaskWriter(tmp_path).apply(handle(tmp_path, "tasks.md"), "toggle")
    assert note.read_text() == "- [x] Task\n"


def test_client_reference_is_validated(tmp_path: Path):
    note = tmp_path / "tasks.md"
    note.write_text("- [ ] Task\n", encoding="utf-8")
    reference = handle(tmp_path, "tasks.md")
    assert EditHandle.from_dict(reference.as_dict()) == reference
    for payload in ({"source": "tasks.md", "line": True, "original": reference.original, "digest": reference.digest},
                    {**reference.as_dict(), "digest": "invalid"},
                    {**reference.as_dict(), "original": "bad\nline"}):
        with pytest.raises(InvalidEdit):
            EditHandle.from_dict(payload)
