import json
from pathlib import Path

from marktask.dashboard import FORM_FIELDS, create_app, form_id, kanban_board, task_table, task_text
from marktask.index import scan
from marktask.links import ObsidianLinks
from marktask.writer import EditHandle, TaskWriter
from test_dashboard import render


def reference(root: Path, source: str = "Work/tasks.md", line: int = 1) -> dict:
    task = next(item for item in scan(root).tasks if item.source == source and item.line == line)
    return EditHandle.from_task(task).as_dict()


def edit_event(app, changed: str, reference: dict, selected=None, proposal=None, form=None,
               quick_date=None, revision=0, lane="Backlog"):
    """Post the same Dash callback inputs/states as the task editor."""
    key = next(name for name in app.callback_map if "edit-status.children" in name)
    button_id = {"key": json.dumps(reference, ensure_ascii=False), "type": "edit-task"}
    due_id = {**button_id, "type": "quick-due"}
    triggered = (button_id if changed == "select" else due_id if changed == "quick-due" else None)
    property_id = (json.dumps(triggered, separators=(",", ":"), sort_keys=True) +
                   (".value" if changed == "quick-due" else ".n_clicks")) if triggered else changed + ".n_clicks"
    inputs = [
        {"id": '{"key":["ALL"],"type":"edit-task"}', "property": "n_clicks",
         "value": [1 if changed == "select" else 0]},
        {"id": '{"key":["ALL"],"type":"quick-due"}', "property": "value",
         "value": [quick_date]},
        *({"id": name, "property": "n_clicks", "value": int(name == changed)}
          for name in ("review-edit", "confirm-edit", "cancel-edit")),
    ]
    fields = form if form is not None else TaskWriter.fields_for(reference["original"])
    states = [
        {"id": "edit-selected", "property": "data", "value": selected},
        {"id": "edit-proposal", "property": "data", "value": proposal},
        *({"id": form_id(name), "property": "value", "value": fields[name]} for name in FORM_FIELDS),
        {"id": "edit-lane", "property": "value", "value": lane},
        {"id": '{"key":["ALL"],"type":"quick-due"}', "property": "id", "value": [due_id]},
        {"id": "edit-revision", "property": "data", "value": revision},
    ]
    response = app.server.test_client().post("/_dash-update-component", json={
        "output": key,
        "outputs": [{"id": name, "property": prop} for name, prop in (
            ("edit-selected", "data"), ("edit-proposal", "data"),
            ("edit-revision", "data"), ("edit-status", "children"),
        )],
        "inputs": inputs, "state": states, "changedPropIds": [property_id],
    })
    assert response.status_code == 200, response.get_data(as_text=True)[:1000]
    return response.get_json()["response"]


def test_read_only_dashboard_has_no_edit_controls(tmp_path: Path):
    (tmp_path / "tasks.md").write_text("- [ ] Task\n", encoding="utf-8")
    app = create_app(tmp_path)
    assert "edit-status.children" not in str(app.callback_map)
    assert b"edit-panel" not in app.server.test_client().get("/_dash-layout").data
    assert "quick-due" not in str(render(app, "?view=all")["results"])
    assert "edit-task" not in str(render(app, "?view=all")["results"])


def test_idle_editor_does_not_show_select_a_task_banner(tmp_path: Path):
    folder = tmp_path / "Work"
    folder.mkdir()
    (folder / "tasks.md").write_text("- [ ] Task\n", encoding="utf-8")
    app = create_app(tmp_path, allow_writes=True)
    result = edit_event(app, "review-edit", reference(tmp_path), selected=None)
    assert result["edit-status"]["children"] == ""


def test_lane_creation_is_collapsed_and_uses_scoped_dark_controls(tmp_path: Path):
    (tmp_path / "tasks.md").write_text("- [ ] Task\n", encoding="utf-8")
    app = create_app(tmp_path, allow_writes=True)
    client = app.server.test_client()
    layout = client.get("/_dash-layout").get_json()

    def find(component):
        if isinstance(component, dict):
            if component.get("props", {}).get("id") == "new-lane-controls":
                return component
            for value in component.values():
                result = find(value)
                if result is not None:
                    return result
        if isinstance(component, list):
            for value in component:
                result = find(value)
                if result is not None:
                    return result
        return None

    control = find(layout)
    assert control["type"] == "Details"
    assert control["props"]["style"] == {"display": "none"}
    assert control["props"]["children"][0]["type"] == "Summary"
    assert control["props"].get("open") is not True
    css = client.get("/assets/style.css").get_data(as_text=True)
    assert ".new-lane-row .dash-input-container" in css
    assert ".board-sort-switch .dash-options-list-option:has(input:checked)" in css


def test_clicking_title_edits_and_source_still_opens_obsidian(tmp_path: Path):
    folder = tmp_path / "Work"
    folder.mkdir()
    (folder / "tasks.md").write_text("- [ ] Edit my wording 📅 2026-09-28\n", encoding="utf-8")
    task = scan(tmp_path).tasks[0]
    links = ObsidianLinks(tmp_path)
    assert task_text(task, links, False).href.startswith("obsidian://")
    button = task_text(task, links, True)
    assert button.id["type"] == "edit-task"
    assert button.children == task.text
    assert button.to_plotly_json()["type"] == "Button"
    assert "href" not in button.to_plotly_json()["props"]
    for view in (str(kanban_board([task], links, True)), str(task_table([task], links, True))):
        assert "task-edit-trigger" in view and "quick-due" in view
        assert "obsidian://open?path=" in view


def test_review_cancel_and_confirm_toggle(tmp_path: Path):
    folder = tmp_path / "Work"
    folder.mkdir()
    note = folder / "tasks.md"
    note.write_text("- [ ] Task\n", encoding="utf-8")
    app = create_app(tmp_path, allow_writes=True)
    layout = app.server.test_client().get("/_dash-layout").data
    assert b"edit-panel" in layout and b"review-edit" in layout and b"preview-title" not in layout
    assert "LOCAL · GUARDED EDITING" in str(render(app, "?view=all")["sidebar"])
    selected = reference(tmp_path)
    assert edit_event(app, "select", selected)["edit-selected"]["data"] == selected
    fields = TaskWriter.fields_for(selected["original"])
    fields["status"] = "done"
    reviewed = edit_event(app, "review-edit", selected, selected=selected, form=fields)
    assert "edit-selected" not in reviewed
    proposal = reviewed["edit-proposal"]["data"]
    assert proposal["after"] == "- [x] Task"
    assert note.read_text() == "- [ ] Task\n"
    assert edit_event(app, "cancel-edit", selected, selected=selected,
                      proposal=proposal)["edit-selected"]["data"] is None
    assert note.read_text() == "- [ ] Task\n"
    saved = edit_event(app, "confirm-edit", selected, selected=selected, proposal=proposal, form=fields)
    assert "Saved" in saved["edit-status"]["children"]
    assert note.read_text() == "- [x] Task\n"


def test_multifield_edit_and_changed_form_guard(tmp_path: Path):
    folder = tmp_path / "Work"
    folder.mkdir()
    note = folder / "tasks.md"
    note.write_text("- [ ] ToDos und Posten abklären 📅 2026-09-28\n", encoding="utf-8")
    app = create_app(tmp_path, allow_writes=True)
    selected = reference(tmp_path)
    fields = TaskWriter.fields_for(selected["original"])
    fields.update(title="ToDos und Posten erledigen", due="2026-10-01", priority="high", tags="#work")
    reviewed = edit_event(app, "review-edit", selected, selected=selected, form=fields)
    assert "edit-selected" not in reviewed
    proposal = reviewed["edit-proposal"]["data"]
    assert proposal["after"] == "- [ ] ToDos und Posten erledigen 📅 2026-10-01 ⏫ #work"
    assert note.read_text() == "- [ ] ToDos und Posten abklären 📅 2026-09-28\n"
    changed = {**fields, "title": "Changed after review"}
    refused = edit_event(app, "confirm-edit", selected, selected=selected, proposal=proposal, form=changed)
    assert "review again" in refused["edit-status"]["children"]
    assert note.read_text().startswith("- [ ] ToDos und Posten abklären")
    saved = edit_event(app, "confirm-edit", selected, selected=selected, proposal=proposal, form=fields)
    assert "Saved" in saved["edit-status"]["children"]
    assert note.read_text() == proposal["after"] + "\n"


def test_form_prefill_and_confirm_button_reflect_current_review(tmp_path: Path):
    folder = tmp_path / "Work"
    folder.mkdir()
    (folder / "tasks.md").write_text("- [ ] Task 📅 2026-09-28 ⏫ #work\n", encoding="utf-8")
    app = create_app(tmp_path, allow_writes=True)
    selected = reference(tmp_path)
    key = next(name for name in app.callback_map if "edit-title.value" in name)
    response = app.server.test_client().post("/_dash-update-component", json={
        "output": key,
        "outputs": [{"id": form_id(name), "property": "value"} for name in FORM_FIELDS] +
                   [{"id": "edit-lane", "property": "value"}],
        "inputs": [{"id": "edit-selected", "property": "data", "value": selected}],
        "state": [{"id": "edit-proposal", "property": "data", "value": None}],
        "changedPropIds": ["edit-selected.data"],
    })
    assert response.status_code == 200
    assert response.get_json()["response"]["edit-title"]["value"] == "Task"
    assert response.get_json()["response"]["edit-priority"]["value"] == "high"
    assert response.get_json()["response"]["edit-lane"]["value"] == "Backlog"

    form = TaskWriter.fields_for(selected["original"])
    form["title"] = "Revised"
    proposal = edit_event(app, "review-edit", selected, selected=selected, form=form)["edit-proposal"]["data"]
    key = next(name for name in app.callback_map if "confirm-edit.disabled" in name)

    def show(fields):
        response = app.server.test_client().post("/_dash-update-component", json={
            "output": key,
            "outputs": [{"id": name, "property": prop} for name, prop in (
                ("edit-panel", "style"), ("edit-selection", "children"),
                ("edit-diff", "children"), ("confirm-edit", "disabled"),
            )],
            "inputs": [
                {"id": "edit-selected", "property": "data", "value": selected},
                {"id": "edit-proposal", "property": "data", "value": proposal},
                *({"id": form_id(name), "property": "value", "value": fields[name]} for name in FORM_FIELDS),
                {"id": "edit-lane", "property": "value", "value": "Backlog"},
            ],
            "state": [], "changedPropIds": ["edit-proposal.data"],
        })
        assert response.status_code == 200
        return response.get_json()["response"]

    assert show(form)["confirm-edit"]["disabled"] is False
    assert "obsidian://open?path=" in str(show(form)["edit-selection"]["children"])
    assert "tasks.md:1" in str(show(form)["edit-selection"]["children"])
    assert show({**form, "title": "Changed after review"})["confirm-edit"]["disabled"] is True


def test_status_and_priority_are_reactive_dropdowns(tmp_path: Path):
    folder = tmp_path / "Work"
    folder.mkdir()
    note = folder / "tasks.md"
    note.write_text("- [ ] Task\n", encoding="utf-8")
    app = create_app(tmp_path, allow_writes=True)
    layout = app.server.test_client().get("/_dash-layout").get_json()

    def component_with_id(component, component_id):
        if isinstance(component, dict):
            if component.get("props", {}).get("id") == component_id:
                return component
            for value in component.values():
                found = component_with_id(value, component_id)
                if found is not None:
                    return found
        elif isinstance(component, list):
            for value in component:
                found = component_with_id(value, component_id)
                if found is not None:
                    return found
        return None

    for component_id, initial, selected in (
        ("edit-status-choice", "todo", "done"), ("edit-priority", "normal", "high"),
    ):
        component = component_with_id(layout, component_id)
        assert component["namespace"] == "dash_core_components"
        assert component["type"] == "Dropdown"
        assert component["props"]["value"] == initial
        assert component["props"]["clearable"] is False
        assert selected in {option["value"] for option in component["props"]["options"]}

    selected = reference(tmp_path)
    fields = TaskWriter.fields_for(selected["original"])
    fields.update(status="done", priority="high")
    proposal = edit_event(app, "review-edit", selected, selected=selected, form=fields)["edit-proposal"]["data"]
    assert proposal["after"] == "- [x] Task ⏫"
    assert note.read_text() == "- [ ] Task\n"
    saved = edit_event(app, "confirm-edit", selected, selected=selected, proposal=proposal, form=fields)
    assert "Saved" in saved["edit-status"]["children"]
    assert note.read_text() == "- [x] Task ⏫\n"


def test_calendar_preview_and_conflict(tmp_path: Path):
    folder = tmp_path / "Work"
    folder.mkdir()
    note = folder / "tasks.md"
    note.write_text("- [ ] Task ^abc\n", encoding="utf-8")
    app = create_app(tmp_path, allow_writes=True)
    selected = reference(tmp_path)
    quick = edit_event(app, "quick-due", selected, quick_date="2026-10-01")
    proposal = quick["edit-proposal"]["data"]
    assert "📅 2026-10-01 ^abc" in proposal["after"]
    assert note.read_text() == "- [ ] Task ^abc\n"
    note.write_text("- [ ] Task ^abc\nAdded in Obsidian\n", encoding="utf-8")
    stale = edit_event(app, "confirm-edit", selected, selected=selected, proposal=proposal,
                       form=proposal["fields"])
    assert "changed" in stale["edit-status"]["children"]
    assert note.read_text().startswith("- [ ] Task ^abc\n")


def test_recurring_status_change_is_blocked(tmp_path: Path):
    folder = tmp_path / "Work"
    folder.mkdir()
    (folder / "tasks.md").write_text("- [ ] Weekly 🔁 every week 📅 2026-10-01\n", encoding="utf-8")
    app = create_app(tmp_path, allow_writes=True)
    selected = reference(tmp_path)
    fields = TaskWriter.fields_for(selected["original"])
    fields["status"] = "done"
    refused = edit_event(app, "review-edit", selected, selected=selected, form=fields)
    assert "Recurring" in refused["edit-status"]["children"]
    assert refused["edit-proposal"]["data"] is None


def test_edit_dialog_combines_lane_title_and_priority_in_one_confirmation(tmp_path: Path):
    folder = tmp_path / "Work"
    folder.mkdir()
    (folder / "_Work.md").write_text("# Work\n", encoding="utf-8")
    board = folder / "_Kanban Work.md"
    board.write_text("---\nkanban-plugin: board\n---\n## Backlog\n\n## Doing\n", encoding="utf-8")
    note = folder / "tasks.md"
    note.write_text("- [ ] Plan #todo\n", encoding="utf-8")
    app = create_app(tmp_path, allow_writes=True)
    handle = reference(tmp_path)
    fields = TaskWriter.fields_for(handle["original"])
    fields.update(title="Revised plan", priority="high")
    reviewed = edit_event(app, "review-edit", handle, selected=handle, form=fields, lane="Doing")
    proposal = reviewed["edit-proposal"]["data"]
    assert proposal["after"] == "- [ ] Revised plan ⏫ #todo/doing"
    assert note.read_text() == "- [ ] Plan #todo\n"
    assert board.read_text().endswith("## Doing\n")
    refused = edit_event(app, "confirm-edit", handle, selected=handle, proposal=proposal,
                         form=fields, lane="Backlog")
    assert "review again" in refused["edit-status"]["children"]
    saved = edit_event(app, "confirm-edit", handle, selected=handle, proposal=proposal,
                       form=fields, lane="Doing")
    assert "Saved" in saved["edit-status"]["children"]
    assert note.read_text() == proposal["after"] + "\n"
    assert board.read_text().endswith("## Doing\n")


def test_create_lane_from_editor_is_separate_from_task_edit(tmp_path: Path):
    folder = tmp_path / "Work"
    folder.mkdir()
    (folder / "_Work.md").write_text("# Work\n", encoding="utf-8")
    board = folder / "_Kanban Work.md"
    board.write_text("---\nkanban-plugin: board\n---\n## Backlog\n", encoding="utf-8")
    note = folder / "tasks.md"
    note.write_text("- [ ] Task #todo\n", encoding="utf-8")
    app = create_app(tmp_path, allow_writes=True)
    handle = reference(tmp_path)
    selected = edit_event(app, "select", handle)["edit-selected"]["data"]
    key = next(key for key in app.callback_map if "lane-status.children" in key)

    def action(trigger, proposal=None, revision=0):
        response = app.server.test_client().post("/_dash-update-component", json={
            "output": key,
            "outputs": [{"id": name, "property": prop} for name, prop in (
                ("lane-proposal", "data"), ("lane-revision", "data"), ("lane-status", "children"),
                ("edit-selected", "data"))],
            "inputs": [{"id": name, "property": "n_clicks", "value": int(name == trigger)} for name in
                       ("preview-lane", "confirm-lane", "cancel-lane")],
            "state": [{"id": "edit-selected", "property": "data", "value": selected},
                      {"id": "new-lane-name", "property": "value", "value": "Team Review"},
                      {"id": "lane-proposal", "property": "data", "value": proposal},
                      {"id": "lane-revision", "property": "data", "value": revision}],
            "changedPropIds": [trigger + ".n_clicks"],
        })
        assert response.status_code == 200, response.get_data(as_text=True)[:800]
        return response.get_json()["response"]

    proposal = action("preview-lane")["lane-proposal"]["data"]
    assert proposal["after"] == "## Team Review"
    assert board.read_text().endswith("## Backlog\n")
    saved = action("confirm-lane", proposal=proposal)
    assert "Lane created" in saved["lane-status"]["children"]
    assert "## Team Review" in board.read_text()
    assert note.read_text() == "- [ ] Task #todo\n"
    choices_key = next(key for key in app.callback_map if "edit-lane.options" in key)
    response = app.server.test_client().post("/_dash-update-component", json={
        "output": choices_key,
        "outputs": [{"id": name, "property": prop} for name, prop in (
            ("edit-lane", "options"), ("edit-lane", "disabled"), ("new-lane-controls", "style"))],
        "inputs": [{"id": "edit-selected", "property": "data", "value": selected},
                   {"id": "lane-revision", "property": "data", "value": saved["lane-revision"]["data"]}],
        "state": [], "changedPropIds": ["lane-revision.data"],
    })
    assert response.status_code == 200
    assert "Team Review" in str(response.get_json()["response"]["edit-lane"]["options"])
    fields = TaskWriter.fields_for(handle["original"])
    move_proposal = edit_event(app, "review-edit", handle, selected=selected, form=fields,
                               lane="Team Review")["edit-proposal"]["data"]
    assert move_proposal["after"] == "- [ ] Task #todo/team-review"
    saved_move = edit_event(app, "confirm-edit", handle, selected=selected, proposal=move_proposal,
                            form=fields, lane="Team Review")
    assert "Saved" in saved_move["edit-status"]["children"]
    assert note.read_text() == "- [ ] Task #todo/team-review\n"


def test_editor_combines_native_board_card_edit_and_move(tmp_path: Path):
    folder = tmp_path / "Work"
    folder.mkdir()
    (folder / "_Work.md").write_text("# Work\n", encoding="utf-8")
    board = folder / "_Kanban Work.md"
    board.write_text(
        "---\nkanban-plugin: board\n---\n## Backlog\n- [ ] Parent\n  - [ ] Child\n## Doing\n",
        encoding="utf-8",
    )
    app = create_app(tmp_path, allow_writes=True)
    handle = reference(tmp_path, "Work/_Kanban Work.md", 5)
    fields = TaskWriter.fields_for(handle["original"])
    fields["title"] = "Updated parent"
    proposal = edit_event(app, "review-edit", handle, selected=handle, form=fields,
                          lane="Doing")["edit-proposal"]["data"]
    assert "- [ ] Updated parent\n  - [ ] Child" in proposal["after"]
    assert "## Backlog\n- [ ] Parent" in board.read_text()
    saved = edit_event(app, "confirm-edit", handle, selected=handle, proposal=proposal,
                       form=fields, lane="Doing")
    assert "Saved" in saved["edit-status"]["children"]
    assert "## Doing\n- [ ] Updated parent\n  - [ ] Child" in board.read_text()
