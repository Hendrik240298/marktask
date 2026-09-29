import json
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

import pytest

from marktask.dashboard import create_app
from marktask.visibility import (VisibilityError, VisibilityRules, file_rule_from_input,
                                 is_reference, load_rules, matches, save_rules, validate_pattern)
from test_dashboard import render


def visibility_event(app, trigger: str, pattern: str, proposal=None, revision=0, action="add", kind="file"):
    output = next(key for key in app.callback_map if "visibility-status.children" in key)
    response = app.server.test_client().post("/_dash-update-component", json={
        "output": output,
        "outputs": [{"id": name, "property": prop} for name, prop in (
            ("visibility-proposal", "data"), ("visibility-revision", "data"),
            ("visibility-status", "children"))],
        "inputs": [{"id": name, "property": "n_clicks", "value": int(name == trigger)}
                   for name in ("preview-visibility", "confirm-visibility", "cancel-visibility")],
        "state": [{"id": name, "property": prop, "value": value} for name, prop, value in (
            ("visibility-kind", "value", kind), ("visibility-action", "value", action),
            ("visibility-pattern", "value", pattern),
            ("visibility-proposal", "data", proposal), ("visibility-revision", "data", revision))],
        "changedPropIds": [trigger + ".n_clicks"],
    })
    assert response.status_code == 200, response.get_data(as_text=True)[:800]
    return response.get_json()["response"]


def test_reference_rules_are_distinct_from_scanner_excludes_and_preserve_notes(tmp_path: Path):
    work = tmp_path / "Work"
    archive = work / "archive"
    archive.mkdir(parents=True)
    active = work / "active.md"
    hidden = archive / "checklist.md"
    active.write_text("- [ ] Visible\n", encoding="utf-8")
    hidden.write_text(f"- [ ] Dated reference 📅 {date.today() + timedelta(days=1)}\n", encoding="utf-8")
    (archive / "plain.md").write_text("No task here\n", encoding="utf-8")
    rules_file = tmp_path / ".marktask-visibility.json"
    rules_file.write_text(json.dumps({"reference_globs": ["archive"]}), encoding="utf-8")
    app = create_app(tmp_path)
    for view in ("all", "upcoming", "kanban"):
        content = str(render(app, f"?view={view}" + ("&project=Work" if view == "kanban" else ""))["results"])
        assert "Visible" in content or view == "upcoming"
        assert "Dated reference" not in content
    reference = str(render(app, "?view=reference")["results"])
    assert "Dated reference" in reference and "plain.md" in reference
    assert "archive" in str(render(app)["visibility-rules"])
    assert render(app)["visibility-panel"]["style"] == {}
    assert render(app, "?view=reference")["visibility-panel"]["style"] == {}
    assert render(app, "?view=all")["visibility-panel"]["style"] == {"display": "none"}
    assert b"visibility-controls" not in app.server.test_client().get("/_dash-layout").data
    assert active.read_text(encoding="utf-8") == "- [ ] Visible\n"
    assert hidden.read_text(encoding="utf-8").startswith("- [ ] Dated reference")
    assert is_reference("Work/archive/checklist.md", ("archive",))
    assert not is_reference("Work/active.md", ("archive",))

    callback = next(key for key in app.callback_map if "visibility-panel.open" in key)
    response = app.server.test_client().post("/_dash-update-component", json={
        "output": callback, "outputs": {"id": "visibility-panel", "property": "open"},
        "inputs": [{"id": "url", "property": "search", "value": "?view=reference"}],
        "state": [], "changedPropIds": ["url.search"],
    })
    assert response.status_code == 200
    assert response.get_json()["response"]["visibility-panel"]["open"] is True


def test_template_folder_is_reference_by_default_and_can_be_unhidden(tmp_path: Path):
    folder = tmp_path / "Work" / "templates"
    folder.mkdir(parents=True)
    (folder / "checklist.md").write_text("- [ ] Template step\n", encoding="utf-8")
    app = create_app(tmp_path)
    assert "Template step" not in str(render(app, "?view=all")["results"])
    assert "Template step" in str(render(app, "?view=reference")["results"])
    rules, digest = load_rules(tmp_path / ".marktask-visibility.json")
    assert rules == VisibilityRules()
    save_rules(tmp_path / ".marktask-visibility.json", VisibilityRules(reference_globs=()), digest)
    assert "Template step" in str(render(app, "?view=all")["results"])


def test_reference_rule_requires_review_confirmation_and_rejects_stale_or_invalid_config(tmp_path: Path):
    folder = tmp_path / "Work"
    folder.mkdir()
    note = folder / "tasks.md"
    note.write_text("- [ ] Keep me\n", encoding="utf-8")
    config = tmp_path / ".marktask-visibility.json"
    app = create_app(tmp_path, allow_writes=True)
    preview = visibility_event(app, "preview-visibility", "tasks.md")
    assert not config.exists()
    proposal = preview["visibility-proposal"]["data"]
    assert proposal["affected"]["files"] == ["Work/tasks.md"]
    rejected = visibility_event(app, "confirm-visibility", "other.md", proposal)
    assert "No rule saved" in rejected["visibility-status"]["children"]
    saved = visibility_event(app, "confirm-visibility", "tasks.md", proposal)
    assert "Reference rule saved" in saved["visibility-status"]["children"]
    assert load_rules(config)[0].reference_globs == ("templates", "tasks.md")
    assert note.read_text(encoding="utf-8") == "- [ ] Keep me\n"
    with pytest.raises(VisibilityError, match="review again"):
        save_rules(config, VisibilityRules(reference_globs=()), "missing")
    cancel = visibility_event(app, "cancel-visibility", "tasks.md")
    assert cancel["visibility-proposal"]["data"] is None
    restore = visibility_event(app, "preview-visibility", "tasks.md", action="remove")
    assert restore["visibility-proposal"]["data"]["affected"]["files"] == ["Work/tasks.md"]
    visibility_event(app, "confirm-visibility", "tasks.md", restore["visibility-proposal"]["data"], action="remove")
    assert load_rules(config)[0] == VisibilityRules()
    config.write_text("not JSON", encoding="utf-8")
    unavailable = render(app, "?view=all")
    assert "Visibility configuration error" in str(unavailable["results"])


def test_visibility_config_rejects_symlinks_and_parent_path_globs(tmp_path: Path):
    source = tmp_path / "rules.json"
    source.write_text('{"reference_globs": []}', encoding="utf-8")
    link = tmp_path / "linked.json"
    link.symlink_to(source)
    with pytest.raises(VisibilityError, match="non-symlink"):
        load_rules(link)
    with pytest.raises(VisibilityError, match="relative path glob"):
        validate_pattern("../secrets/*")


def test_gui_task_rules_hide_selected_tasks_without_hiding_their_note(tmp_path: Path):
    work = tmp_path / "Work"
    work.mkdir()
    note = work / "tasks.md"
    note.write_text("- [ ] Keep this\n- [ ] Hide this 📅 2030-01-01\n", encoding="utf-8")
    another = work / "other.md"
    another.write_text("- [ ] Hide this too\n", encoding="utf-8")
    app = create_app(tmp_path, allow_writes=True)
    preview = visibility_event(app, "preview-visibility", "Work/tasks.md :: Hide this", kind="task")
    proposal = preview["visibility-proposal"]["data"]
    assert proposal["affected"]["files"] == []
    assert len(proposal["affected"]["tasks"]) == 1
    assert "Work/tasks.md:2" in proposal["affected"]["tasks"][0]
    assert "Hide this" in str(render(app, "?view=all")["results"])
    visibility_event(app, "confirm-visibility", "Work/tasks.md :: Hide this", proposal, kind="task")
    visible = str(render(app, "?view=all")["results"])
    assert "Keep this" in visible and "Hide this 📅" not in visible
    assert "Hide this too" in visible  # Note-scoped rule, not a global text match.
    reference = str(render(app, "?view=reference")["results"])
    assert "Hide this 📅" in reference and "tasks.md" in reference
    assert load_rules(tmp_path / ".marktask-visibility.json")[0].task_globs == ("Work/tasks.md :: Hide this",)
    assert note.read_text(encoding="utf-8") == "- [ ] Keep this\n- [ ] Hide this 📅 2030-01-01\n"
    assert another.read_text(encoding="utf-8") == "- [ ] Hide this too\n"


def test_task_rule_preview_rejected_if_matching_task_changes(tmp_path: Path):
    note = tmp_path / "tasks.md"
    note.write_text("- [ ] Hide this\n", encoding="utf-8")
    app = create_app(tmp_path, allow_writes=True)
    proposal = visibility_event(app, "preview-visibility", "Hide this", kind="task")["visibility-proposal"]["data"]
    note.write_text("- [ ] Not that\n", encoding="utf-8")
    rejected = visibility_event(app, "confirm-visibility", "Hide this", proposal, kind="task")
    assert "review again" in rejected["visibility-status"]["children"]
    assert not (tmp_path / ".marktask-visibility.json").exists()


def test_absolute_file_and_folder_paths_become_scoped_relative_rules(tmp_path: Path):
    root = tmp_path / "1-Projects"
    folder = root / "Work" / "archive"
    folder.mkdir(parents=True)
    note = folder / "checklist [1].md"
    note.write_text("- [ ] Archived\n", encoding="utf-8")
    other = root / "Other" / "archive"
    other.mkdir(parents=True)
    (other / "checklist [1].md").write_text("- [ ] Keep visible\n", encoding="utf-8")

    exact = file_rule_from_input(str(note), root)
    assert exact.startswith("./Work/archive/")
    assert matches("Work/archive/checklist [1].md", exact)
    assert not matches("Other/archive/checklist [1].md", exact)
    assert file_rule_from_input("file://" + quote(str(note)), root) == exact
    assert file_rule_from_input(str(folder), root) == "./Work/archive/*"
    assert matches("Work/archive/nested/task.md", "./Work/archive/*")
    outside = tmp_path / "outside.md"
    outside.write_text("no access", encoding="utf-8")
    with pytest.raises(VisibilityError, match="inside the selected"):
        file_rule_from_input(str(outside), root)
    with pytest.raises(VisibilityError, match="containing"):
        file_rule_from_input(str(root / "Work" / ".." / "Other"), root)
    (root / "linked.md").symlink_to(note)
    with pytest.raises(VisibilityError, match="Symlinked"):
        file_rule_from_input(str(root / "linked.md"), root)

    app = create_app(root, allow_writes=True)
    preview = visibility_event(app, "preview-visibility", str(folder))["visibility-proposal"]["data"]
    assert preview["pattern"] == "./Work/archive/*"
    assert preview["affected"]["files"] == ["Work/archive/checklist [1].md"]
    visibility_event(app, "confirm-visibility", str(folder), preview)
    stored = (root / ".marktask-visibility.json").read_text(encoding="utf-8")
    assert str(root) not in stored and "./Work/archive/*" in stored
    visible = str(render(app, "?view=all")["results"])
    assert "Archived" not in visible and "Keep visible" in visible
    layout = app.server.test_client().get("/_dash-layout").data
    assert b"visibility-drop" in layout
    assert app.server.test_client().get("/assets/visibility_drop.js").status_code == 200
