from pathlib import Path
from datetime import date, timedelta
import json

from marktask.dashboard import create_app, ordered_table_tasks, route
from marktask.index import scan


def render(app, search="", query=None, sort_by="due", table_sort=None):
    output = next(key for key in app.callback_map if "results.children" in key)
    values = {"refresh.n_clicks": 0, "url.search": search, "query.value": query,
              "board-sort.value": sort_by, "table-sort.data": table_sort or {"column": "due", "direction": "asc"},
              "edit-revision.data": 0, "move-revision.data": 0, "lane-revision.data": 0,
              "visibility-revision.data": 0}
    response = app.server.test_client().post("/_dash-update-component", json={
        "output": output,
        "outputs": [{"id": name, "property": prop} for name, prop in (
            ("sidebar", "children"), ("page-title", "children"), ("summary", "children"),
            ("results", "children"), ("diagnostics", "children"),
            ("visibility-panel", "style"), ("visibility-heading", "children"),
            ("visibility-rules", "children"),
        )],
        "inputs": [{**item, "value": values[f"{item['id']}.{item['property']}"]}
                   for item in app.callback_map[output]["inputs"]],
        "state": [], "changedPropIds": ["url.search"],
    })
    assert response.status_code == 200
    return response.get_json()["response"]


def test_local_dash_entrypoint_serves_page_and_layout(tmp_path: Path):
    (tmp_path / "note.md").write_text("- [ ] Test\n", encoding="utf-8")
    app = create_app(tmp_path)
    client = app.server.test_client()
    assert client.get("/").status_code == 200
    stylesheet = client.get("/assets/style.css")
    assert stylesheet.status_code == 200
    assert b"color-scheme: dark" in stylesheet.data
    assert b"--accent: #d94f49" in stylesheet.data
    assert b"sidebar" in client.get("/_dash-layout").data
    response = render(app, "?view=all")
    assert "note.md:1" in str(response["results"]["children"])
    assert "obsidian://open?path=" in str(response["results"]["children"])
    assert "Inbox" in str(response["sidebar"]["children"])
    assert response["page-title"]["children"] == "All tasks"


def test_sidebar_project_link_opens_kanban_with_backlog_and_native_column(tmp_path: Path):
    project = tmp_path / "Project One"
    project.mkdir()
    (project / "_Project One.md").write_text("# Project One\n", encoding="utf-8")
    (project / "notes.md").write_text("- [ ] Untagged\n- [x] Finished\n", encoding="utf-8")
    (project / "_Kanban Project One.md").write_text(
        "---\nkanban-plugin: board\n---\n## Doing\n- [ ] Native\n", encoding="utf-8",
    )
    app = create_app(tmp_path)
    projects = render(app)
    assert "Project+One" in str(projects["sidebar"]["children"])
    assert "view=kanban" in str(projects["results"]["children"])

    board = render(app, "?view=kanban&project=Project+One")
    assert board["page-title"]["children"] == "Project One"
    content = str(board["results"]["children"])
    assert all(name in content for name in ("Backlog", "Doing", "Done", "Untagged", "Native", "Finished"))
    assert "notes.md:1" in content
    assert "obsidian://open?path=" in content
    assert "nav-link active" in str(board["sidebar"]["children"])
    assert route("?view=kanban&project=Project+One") == ("kanban", "Project One")


def test_inbox_shows_only_explicit_open_tasks(tmp_path: Path):
    project = tmp_path / "Personal"
    project.mkdir()
    (project / "_Personal.md").write_text("# Personal\n", encoding="utf-8")
    (project / "notes.md").write_text(
        "- [ ] Capture #inbox/privat\n- [ ] No tag\n- [x] Finished #inbox\n", encoding="utf-8",
    )
    (project / "_Kanban Personal.md").write_text(
        "---\nkanban-plugin: board\n---\n## Inbox\n- [ ] Native capture\n", encoding="utf-8",
    )
    app = create_app(tmp_path)
    inbox = render(app, "?view=inbox")
    assert inbox["page-title"]["children"] == "Inbox"
    content = str(inbox["results"]["children"])
    assert "Capture" in content and "Native capture" in content
    assert "No tag" not in content and "Finished" not in content


def test_empty_board_lanes_and_nested_project_master_note(tmp_path: Path):
    child = tmp_path / "Parent" / "Child"
    child.mkdir(parents=True)
    (child / "_Child.md").write_text("# Child project\n", encoding="utf-8")
    (child / "_Kanban Child.md").write_text(
        "---\nkanban-plugin: board\n---\n## Backlog\n\n## Doing - Hendrik\n",
        encoding="utf-8",
    )
    app = create_app(tmp_path)
    board = render(app, "?view=kanban&project=Parent%2FChild")
    content = str(board["results"]["children"])
    assert "_Child.md" in content and "Child project" in content
    assert "Backlog" in content and "Doing - Hendrik" in content
    assert "0" in content
    assert route("?view=inbox") == ("inbox", None)


def test_top_level_board_renders_six_lanes_with_ambiguous_master_notes(tmp_path: Path):
    folder = tmp_path / "Work"
    folder.mkdir()
    (folder / "_First.md").write_text("# First\n", encoding="utf-8")
    (folder / "_Second.md").write_text("# Second\n", encoding="utf-8")
    lanes = ("Inbox", "Backlog", "Next", "Doing", "Waiting", "Done")
    (folder / "_Kanban Work.md").write_text(
        "---\nkanban-plugin: board\n---\n" + "\n".join(f"## {lane}" for lane in lanes) + "\n",
        encoding="utf-8")
    app = create_app(tmp_path)
    result = render(app, "?view=kanban&project=Work")["results"]["children"]
    assert "Several _*.md notes" in str(result[0])
    assert len(result[2]["props"]["children"]) == 6
    assert all(lane in str(result[2]["props"]["children"][number])
               for number, lane in enumerate(lanes))


def test_kanban_sort_toggle_changes_order_without_writing(tmp_path: Path):
    folder = tmp_path / "Work"
    folder.mkdir()
    note = folder / "notes.md"
    note.write_text(
        "- [ ] Early low 🔽 📅 2026-10-01\n"
        "- [ ] Normal 📅 2026-10-02\n"
        "- [ ] High later ⏫ 📅 2026-10-03\n"
        "- [ ] Highest later 🔺 📅 2026-10-04\n"
        "- [ ] Medium undated 🔼\n", encoding="utf-8",
    )
    original = note.read_bytes()
    app = create_app(tmp_path)
    due = str(render(app, "?view=kanban&project=Work")["results"]["children"])
    priority = str(render(app, "?view=kanban&project=Work", sort_by="priority")["results"]["children"])
    assert due.index("Early low") < due.index("High later") < due.index("Highest later")
    assert priority.index("Highest later") < priority.index("High later") < priority.index("Medium undated")
    assert priority.index("Medium undated") < priority.index("Normal") < priority.index("Early low")
    assert note.read_bytes() == original

    output = next(key for key in app.callback_map if "board-sort-control.style" in key)
    for route_search, visible in (("?view=kanban&project=Work", True), ("?view=all", False)):
        response = app.server.test_client().post("/_dash-update-component", json={
            "output": output,
            "outputs": {"id": "board-sort-control", "property": "style"},
            "inputs": [{"id": "url", "property": "search", "value": route_search}],
            "state": [], "changedPropIds": ["url.search"],
        })
        assert response.status_code == 200
        assert (response.get_json()["response"]["board-sort-control"]["style"] == {}) is visible


def test_project_page_is_compact_and_workspace_project_names_are_links(tmp_path: Path):
    folder = tmp_path / "Work Notes"
    folder.mkdir()
    (folder / "_Work Notes.md").write_text("# Big project note\n", encoding="utf-8")
    (folder / "tasks.md").write_text("- [ ] Follow up\n", encoding="utf-8")
    app = create_app(tmp_path)
    board = render(app, "?view=kanban&project=Work+Notes")
    assert board["summary"]["children"] == []
    panel = board["results"]["children"][0]
    details = panel["props"]["children"]
    assert details["type"] == "Details"
    assert details["props"].get("open") is not True
    assert details["props"]["children"][0]["type"] == "Summary"
    assert "Big project note" in str(details)

    all_tasks = render(app, "?view=all")
    assert all_tasks["summary"]["children"] == []
    assert render(app)["summary"]["children"]
    table = all_tasks["results"]["children"][1]
    assert "view=kanban&amp;project=Work+Notes" in str(table) or "view=kanban&project=Work+Notes" in str(table)
    css = app.server.test_client().get("/assets/style.css").get_data(as_text=True)
    assert "max-width: 1580px" not in css


def test_subtasks_stay_off_board_but_keep_their_due_views_and_context(tmp_path: Path):
    from marktask.index import parse_markdown, scan, task_column
    from marktask.dashboard import task_detail_context
    from marktask.links import ObsidianLinks

    folder = tmp_path / "Work"
    folder.mkdir()
    text = ("- [ ] Parent #todo\n"
            "  - Reason to do it\n"
            f"  - [ ] Child 📅 {date.today() + timedelta(days=1)}\n"
            "    - Child note\n"
            f"    - [ ] Grandchild 📅 {date.today() + timedelta(days=2)}\n"
            "- [ ] Sibling\n")
    (folder / "tasks.md").write_text(text, encoding="utf-8")
    tasks, warnings = parse_markdown(text, "Work/tasks.md", "Work")
    assert warnings == []
    assert [(task.text.split()[0], task.parent_line, task.notes) for task in tasks] == [
        ("Parent", None, ("Reason to do it",)),
        ("Child", 1, ("Child note",)),
        ("Grandchild", 3, ()),
        ("Sibling", None, ()),
    ]
    app = create_app(tmp_path, allow_writes=True)
    board = str(render(app, "?view=kanban&project=Work")["results"]["children"])
    assert "2 tasks" in board and "1 subtask" in board
    assert "Child 📅" not in board and "Grandchild 📅" not in board
    upcoming = str(render(app, "?view=upcoming")["results"]["children"])
    assert "Child 📅" in upcoming and "Grandchild 📅" in upcoming
    indexed = scan(tmp_path).tasks
    assert task_column(indexed[1]) == task_column(indexed[0])
    details = str(task_detail_context(tasks[0], tuple(tasks), ObsidianLinks(tmp_path, None)))
    assert "Reason to do it" in details and "Child 📅" in details
    child_details = str(task_detail_context(tasks[1], tuple(tasks), ObsidianLinks(tmp_path, None)))
    assert "Child note" in child_details and "Grandchild 📅" in child_details
    assert "Subtask of" in child_details and "Parent" in child_details


def test_subtask_fields_can_be_edited_without_changing_inherited_lane(tmp_path: Path):
    from marktask.index import scan, task_column
    from marktask.writer import EditHandle, TaskWriter

    folder = tmp_path / "Work"
    folder.mkdir()
    (folder / "_Work.md").write_text("# Work\n", encoding="utf-8")
    (folder / "_Kanban Work.md").write_text(
        "---\nkanban-plugin: board\n---\n## Doing\n", encoding="utf-8")
    note = folder / "tasks.md"
    note.write_text("- [ ] Parent #todo/doing\n  - [ ] Child\n", encoding="utf-8")
    parent, child = (task for task in scan(tmp_path).tasks if task.source == "Work/tasks.md")
    assert task_column(parent) == task_column(child) == "Doing"
    writer = TaskWriter(tmp_path)
    handle = EditHandle.from_task(child)
    fields = writer.fields_for(child.original)
    fields["due"] = "2026-10-03"
    preview = writer.preview_change(handle, fields, "Doing")
    assert "📅 2026-10-03" in preview.after
    writer.apply_change(handle, fields, "Doing", preview.after)
    assert note.read_text(encoding="utf-8") == "- [ ] Parent #todo/doing\n  - [ ] Child 📅 2026-10-03\n"


def test_task_wikilinks_offer_real_obsidian_note_links(tmp_path: Path):
    from marktask.dashboard import task_detail_context
    from marktask.index import scan
    from marktask.links import ObsidianLinks

    folder = tmp_path / "Work"
    folder.mkdir()
    (folder / "Gästeliste.md").write_text("Guest list\n", encoding="utf-8")
    (folder / "tasks.md").write_text(
        "- [ ] Discuss [[Gästeliste|guests]]\n  - Refer to [[Gästeliste]]\n", encoding="utf-8")
    app = create_app(tmp_path, allow_writes=True)
    board = str(render(app, "?view=kanban&project=Work")["results"])
    assert "obsidian://open?path=" in board and "G%C3%A4steliste.md" in board
    assert "guests" in board
    index = scan(tmp_path)
    context = str(task_detail_context(index.tasks[0], index.tasks, ObsidianLinks(tmp_path), index.sources))
    assert "G%C3%A4steliste.md" in context


def test_workspace_tables_show_priority_and_sort_before_limiting_rows(tmp_path: Path):
    folder = tmp_path / "Work"
    folder.mkdir()
    note = folder / "tasks.md"
    today = date.today()
    note.write_text(
        f"- [ ] Alpha low 🔽 📅 {today + timedelta(days=1)} #inbox\n"
        f"- [ ] Zulu high ⏫ 📅 {today + timedelta(days=2)} #inbox\n"
        "- [ ] Undated highest 🔺 #inbox\n", encoding="utf-8")
    original = note.read_bytes()
    app = create_app(tmp_path)

    due = str(render(app, "?view=inbox")["results"])
    highest = str(render(app, "?view=inbox", table_sort={"column": "priority", "direction": "desc"})["results"])
    lowest = str(render(app, "?view=inbox", table_sort={"column": "priority", "direction": "asc"})["results"])
    latest = str(render(app, "?view=inbox", table_sort={"column": "due", "direction": "desc"})["results"])
    assert due.index("Alpha low") < due.index("Zulu high") < due.index("Undated highest")
    assert highest.index("Undated highest") < highest.index("Zulu high") < highest.index("Alpha low")
    assert lowest.index("Alpha low") < lowest.index("Zulu high") < lowest.index("Undated highest")
    assert latest.index("Zulu high") < latest.index("Alpha low") < latest.index("Undated highest")
    assert "Priority" in due and "High ⏫" in due and "Lowest" not in due
    assert "aria-sort" in due and "ascending" in due
    assert "table-sort-button" in due
    assert note.read_bytes() == original

    dated = str(render(app, "?view=upcoming", table_sort={"column": "priority", "direction": "desc"})["results"])
    assert dated.index("Zulu high") < dated.index("Alpha low")
    assert "Undated highest" not in dated

    note.write_text("".join(f"- [ ] Item {number}\n" for number in range(151))
                    + "- [ ] Urgent 🔺\n", encoding="utf-8")
    top = str(render(app, "?view=all", table_sort={"column": "priority", "direction": "desc"})["results"])
    assert "Urgent 🔺" in top and "Showing first 150" in top


def test_column_header_click_toggles_and_other_headers_start_sensibly(tmp_path: Path):
    (tmp_path / "tasks.md").write_text("- [ ] Example\n", encoding="utf-8")
    app = create_app(tmp_path)
    key = next(name for name in app.callback_map if "table-sort.data" in name)

    def click(column, current):
        identity = {"type": "table-sort", "column": column}
        response = app.server.test_client().post("/_dash-update-component", json={
            "output": key, "outputs": {"id": "table-sort", "property": "data"},
            "inputs": [{"id": '{"column":["ALL"],"type":"table-sort"}',
                        "property": "n_clicks", "value": [1]}],
            "state": [{"id": "table-sort", "property": "data", "value": current}],
            "changedPropIds": [json.dumps(identity, sort_keys=True, separators=(",", ":")) + ".n_clicks"],
        })
        assert response.status_code == 200, response.get_data(as_text=True)[:500]
        return response.get_json()["response"]["table-sort"]["data"]

    initial = {"column": "due", "direction": "asc"}
    due_desc = click("due", initial)
    assert due_desc == {"column": "due", "direction": "desc"}
    assert click("due", due_desc) == initial
    priority = click("priority", initial)
    assert priority == {"column": "priority", "direction": "desc"}
    assert click("priority", priority) == {"column": "priority", "direction": "asc"}
    assert click("project", priority) == {"column": "project", "direction": "asc"}

    tasks = list(scan(tmp_path).tasks)
    assert ordered_table_tasks(tasks, {"column": "unknown", "direction": "desc"}) == tasks
