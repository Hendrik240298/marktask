from datetime import date
from pathlib import Path

import pytest

from marktask.index import scan, visible_tasks
from marktask.writer import EditHandle, InvalidEdit, TaskWriter, UnsupportedTask


def setup_note(tmp_path: Path, line: str) -> tuple[Path, TaskWriter, EditHandle]:
    note = tmp_path / "task.md"
    note.write_bytes((line + "\r\nOther unchanged\n").encode("utf-8"))
    task = scan(tmp_path).tasks[0]
    return note, TaskWriter(tmp_path), EditHandle.from_task(task)


def test_read_and_update_multiple_tasks_plugin_fields_in_one_line(tmp_path: Path):
    original = "- [ ] Write report #work ⏳ 2026-10-01 📅 2026-10-03 🔁 every week ⏫ 🆔 own ⛔ blocker ^abc"
    note, writer, handle = setup_note(tmp_path, original)
    fields = writer.fields_for(original)
    assert fields["title"] == "Write report"
    assert (fields["due"], fields["scheduled"], fields["priority"], fields["tags"], fields["recurrence"]) == (
        "2026-10-03", "2026-10-01", "high", "#work", "every week",
    )
    (tmp_path / "blocker.md").write_text("- [ ] Blocking 🆔 blocker\n", encoding="utf-8")
    fields.update(title="Finish report", due="2026-10-04", priority="highest", tags="#next #urgent",
                  scheduled="", start="2026-09-30", recurrence="every 2 weeks", depends_on="blocker")
    preview = writer.preview(handle, "fields", fields=fields)
    assert preview.after == ("- [ ] Finish report 📅 2026-10-04 🔁 every 2 weeks "
                             "🔺 🆔 own ⛔ blocker 🛫 2026-09-30 #next #urgent ^abc")
    assert note.read_bytes().startswith(original.encode("utf-8"))
    writer.apply(handle, "fields", fields=fields, expected_after=preview.after)
    assert note.read_bytes() == (preview.after + "\r\nOther unchanged\n").encode("utf-8")


def test_created_done_cancelled_and_status_changes(tmp_path: Path):
    note, writer, handle = setup_note(tmp_path, "- [ ] Item 📅 2026-10-01")
    fields = writer.fields_for(handle.original)
    fields.update(status="cancelled", created="2026-09-01", cancelled="2026-09-30")
    writer.apply(handle, "fields", fields=fields)
    assert note.read_text().splitlines()[0].startswith("- [-] Item 📅 2026-10-01 ➕ 2026-09-01 ❌ 2026-09-30")
    assert not visible_tasks(scan(tmp_path).tasks, "today", date(2026, 10, 1))
    from marktask.dashboard import project_cards, summary
    assert "0 open" in str(project_cards(scan(tmp_path), list(scan(tmp_path).tasks)))
    assert summary(scan(tmp_path), date(2026, 10, 1))[1].children[1].children == "0"
    handle = EditHandle.from_task(scan(tmp_path).tasks[0])
    fields = writer.fields_for(handle.original)
    fields.update(status="done", cancelled="", done="2026-10-02")
    writer.apply(handle, "fields", fields=fields)
    assert note.read_text().splitlines()[0].endswith("➕ 2026-09-01 ✅ 2026-10-02")


@pytest.mark.parametrize("field,value", [
    ("due", "2026-02-30"), ("start", "tomorrow"), ("priority", "urgent"),
    ("tags", "work"), ("recurrence", "every someday"),
    ("recurrence", "every weekdays"), ("depends_on", "unknown"),
])
def test_invalid_form_value_does_not_touch_file(tmp_path: Path, field: str, value: str):
    note, writer, handle = setup_note(tmp_path, "- [ ] Item 📅 2026-10-01")
    fields = writer.fields_for(handle.original)
    fields[field] = value
    with pytest.raises((InvalidEdit, UnsupportedTask)):
        writer.apply(handle, "fields", fields=fields)
    assert note.read_text().startswith("- [ ] Item 📅 2026-10-01\n")


def test_recurring_task_cannot_be_completed_or_cancelled(tmp_path: Path):
    _, writer, handle = setup_note(tmp_path, "- [ ] Check weekly 🔁 every week 📅 2026-10-01")
    for status in ("done", "cancelled"):
        fields = writer.fields_for(handle.original)
        fields["status"] = status
        with pytest.raises(UnsupportedTask, match="Recurring"):
            writer.preview(handle, "fields", fields=fields)


def test_duplicate_dates_and_tags_inside_links_fail_closed(tmp_path: Path):
    _, writer, handle = setup_note(tmp_path, "- [ ] Check 📅 2026-10-01 📅 2026-10-03")
    with pytest.raises(UnsupportedTask, match="Multiple due"):
        writer.fields_for(handle.original)


def test_prefix_tag_kept_when_editing_title(tmp_path: Path):
    note, writer, handle = setup_note(tmp_path, "- [ ] #task Original title 📅 2026-10-01 ^abc")
    fields = writer.fields_for(handle.original)
    assert fields["title"] == "Original title" and fields["tags"] == "#task"
    fields["title"] = "Revised title"
    writer.apply(handle, "fields", fields=fields)
    assert note.read_text().splitlines()[0] == "- [ ] #task Revised title 📅 2026-10-01 ^abc"


def test_text_after_tag_refused_instead_of_silently_preserved_as_metadata(tmp_path: Path):
    _, writer, handle = setup_note(tmp_path, "- [ ] Review #work then send")
    with pytest.raises(UnsupportedTask, match="ambiguous"):
        writer.fields_for(handle.original)


def test_stale_multifield_preview_does_not_overwrite_external_edit(tmp_path: Path):
    note, writer, handle = setup_note(tmp_path, "- [ ] Task 📅 2026-10-01")
    fields = writer.fields_for(handle.original)
    fields.update(priority="medium", due="2026-10-02")
    preview = writer.preview(handle, "fields", fields=fields)
    note.write_text("- [ ] Task 📅 2026-10-01\nExternal change\n", encoding="utf-8")
    from marktask.writer import StaleSnapshot
    with pytest.raises(StaleSnapshot):
        writer.apply(handle, "fields", fields=fields, expected_after=preview.after)
    assert note.read_text().endswith("External change\n")


def test_dependency_requires_unique_existing_id_and_refuses_cycle(tmp_path: Path):
    note, writer, handle = setup_note(tmp_path, "- [ ] Parent 🆔 parent")
    (tmp_path / "child.md").write_text("- [ ] Child 🆔 child ⛔ parent\n", encoding="utf-8")
    fields = writer.fields_for(handle.original)
    fields["depends_on"] = "child"
    with pytest.raises(InvalidEdit, match="cycle"):
        writer.preview(handle, "fields", fields=fields)
    fields["depends_on"] = "unknown"
    with pytest.raises(UnsupportedTask, match="exactly one"):
        writer.preview(handle, "fields", fields=fields)
    assert note.read_text().startswith("- [ ] Parent 🆔 parent")
