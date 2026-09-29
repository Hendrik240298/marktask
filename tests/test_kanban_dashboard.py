import json
from pathlib import Path

from marktask.dashboard import create_app
from marktask.index import scan
from marktask.writer import EditHandle
from test_dashboard import render


def move_event(app, changed: str, request=None, proposal=None, revision=0):
    key = next(name for name in app.callback_map if "move-status.children" in name)
    inputs = [
        {"id": "move-request", "property": "data", "value": request},
        {"id": "confirm-move", "property": "n_clicks", "value": int(changed == "confirm-move")},
        {"id": "cancel-move", "property": "n_clicks", "value": int(changed == "cancel-move")},
    ]
    response = app.server.test_client().post("/_dash-update-component", json={
        "output": key,
        "outputs": [{"id": name, "property": prop} for name, prop in (
            ("move-proposal", "data"), ("move-revision", "data"), ("move-status", "children"))],
        "inputs": inputs,
        "state": [{"id": "move-proposal", "property": "data", "value": proposal},
                  {"id": "move-revision", "property": "data", "value": revision}],
        "changedPropIds": [changed + (".data" if changed == "move-request" else ".n_clicks")],
    })
    assert response.status_code == 200, response.get_data(as_text=True)[:800]
    return response.get_json()["response"]


def project(tmp_path: Path) -> tuple[Path, Path]:
    folder = tmp_path / "Work"
    folder.mkdir()
    (folder / "_Work.md").write_text("# Work\n", encoding="utf-8")
    board = folder / "_Kanban Work.md"
    board.write_text("---\nkanban-plugin: board\n---\n## Backlog\n\n## Doing - Hendrik\n",
                     encoding="utf-8")
    note = folder / "notes.md"
    note.write_text("- [ ] Work item #todo/privat\n", encoding="utf-8")
    return board, note


def request_for(root: Path, source: str, line: int, destination: str) -> dict:
    task = next(task for task in scan(root).tasks if task.source == source and task.line == line)
    return {"key": json.dumps(EditHandle.from_task(task).as_dict(), ensure_ascii=False),
            "destination": destination, "nonce": 1}


def test_drag_drop_previews_before_confirming_and_preserves_context(tmp_path: Path):
    board, note = project(tmp_path)
    app = create_app(tmp_path, allow_writes=True)
    client = app.server.test_client()
    assert client.get("/assets/kanban_drag.js").status_code == 200
    layout = client.get("/_dash-layout").data
    assert b"move-request" in layout and b"confirm-move" in layout
    shown = str(render(app, "?view=kanban&project=Work")["results"]["children"])
    assert "data-move-key" in shown and "data-move-lane" in shown
    assert "Doing - Hendrik" in shown and "'children': '0'" in shown

    request = request_for(tmp_path, "Work/notes.md", 1, "Doing - Hendrik")
    preview = move_event(app, "move-request", request=request)
    proposal = preview["move-proposal"]["data"]
    assert proposal["after"] == "- [ ] Work item #todo/privat #todo/doing-hendrik"
    preview_key = next(key for key in app.callback_map if "move-panel.style" in key)
    dialog = client.post("/_dash-update-component", json={
        "output": preview_key,
        "outputs": [{"id": name, "property": prop} for name, prop in (
            ("move-panel", "style"), ("move-selection", "children"), ("move-diff", "children"))],
        "inputs": [{"id": "move-proposal", "property": "data", "value": proposal}],
        "state": [], "changedPropIds": ["move-proposal.data"],
    })
    assert dialog.status_code == 200
    assert "Before:" in dialog.get_json()["response"]["move-diff"]["children"]
    assert "Doing - Hendrik" in dialog.get_json()["response"]["move-selection"]["children"]
    assert note.read_text() == "- [ ] Work item #todo/privat\n"
    assert board.read_text().endswith("## Doing - Hendrik\n")
    cancelled = move_event(app, "cancel-move", proposal=proposal)
    assert cancelled["move-proposal"]["data"] is None
    assert note.read_text() == "- [ ] Work item #todo/privat\n"
    saved = move_event(app, "confirm-move", proposal=proposal)
    assert "Moved" in saved["move-status"]["children"]
    assert note.read_text() == proposal["after"] + "\n"
    assert board.read_text().endswith("## Doing - Hendrik\n")


def test_drag_drop_stale_preview_and_read_only_mode(tmp_path: Path):
    _board, note = project(tmp_path)
    readonly = create_app(tmp_path)
    assert b"move-request" not in readonly.server.test_client().get("/_dash-layout").data
    shown = str(render(readonly, "?view=kanban&project=Work")["results"]["children"])
    assert "data-move-key" not in shown and "data-move-lane" not in shown

    app = create_app(tmp_path, allow_writes=True)
    request = request_for(tmp_path, "Work/notes.md", 1, "Doing - Hendrik")
    proposal = move_event(app, "move-request", request=request)["move-proposal"]["data"]
    note.write_text(note.read_text() + "Changed in Obsidian\n", encoding="utf-8")
    refused = move_event(app, "confirm-move", proposal=proposal)
    assert "changed" in refused["move-status"]["children"]
    assert note.read_text().endswith("Changed in Obsidian\n")
