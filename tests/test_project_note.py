import os
from pathlib import Path

from marktask.project_note import load_project_note, preview_markdown
from test_dashboard import render
from marktask.dashboard import create_app


def test_exact_note_renders_properties_and_body_above_tasks(tmp_path: Path):
    folder = tmp_path / "Project One"
    folder.mkdir()
    master = folder / "_Project One.md"
    master.write_text(
        "\ufeff---\ncreated: 2026-09-28\npriority: 2\ncategory: [learning, work]\nstatus: active\n---\n"
        "# Goal\nGeneral project **context**.\n\n- [ ] A real task\n",
        encoding="utf-8",
    )
    (folder / "_Other.md").write_text("Wrong note", encoding="utf-8")
    (folder / "_Kanban Project One.md").write_text("Wrong board", encoding="utf-8")
    app = create_app(tmp_path)
    result = render(app, "?view=kanban&project=Project+One")
    components = result["results"]["children"]
    panel = components[0]
    assert panel["props"]["className"] == "project-note"
    displayed = str(panel)
    assert "2026-09-28" in displayed and "learning, work" in displayed
    assert "General project **context**" in displayed
    assert "obsidian://open?path=" in displayed and "_Project%20One.md" in displayed
    assert "Wrong note" not in displayed and "Wrong board" not in displayed
    assert "A real task" in str(components[2])
    assert master.read_text(encoding="utf-8").startswith("\ufeff---")


def test_safe_obsidian_preview_handles_callouts_soft_breaks_and_wikilinks():
    text = ("uplinks: [[__Projects]]\nrelated:\ntags: #project\n\n"
            ">[!question] What is the goal?\n> Answer here.\n\n"
            "## Notes\n- [[Gästeliste|Guest list]]\n- [ ] First\n- [ ] Second\n\n"
            "```md\n>[!question] untouched\n[[raw]]\n```\n")
    result = preview_markdown(text)
    assert "uplinks: __Projects  \nrelated:  \ntags: #project" in result
    assert "> **Question** What is the goal?\n> Answer here." in result
    assert "- Guest list\n- [ ] First\n- [ ] Second" in result
    assert "```md\n>[!question] untouched\n[[raw]]\n```" in result
    assert "<script" not in result


def test_project_note_links_real_files_and_escapes_untrusted_html(tmp_path: Path):
    work = tmp_path / "Work"
    work.mkdir()
    note = work / "_Work.md"
    note.write_text("---\nrelated: '[[Gästeliste]]'\n---\n"
                    "# Goal\n>[!question] Link to [[Gästeliste|Guest list]]\n- [[Missing]]\n"
                    "<img src=x onerror=alert(1)>\n", encoding="utf-8")
    (work / "Gästeliste.md").write_text("A real note\n", encoding="utf-8")
    app = create_app(tmp_path)
    result = render(app, "?view=kanban&project=Work")
    displayed = str(result["results"]["children"][0])
    assert "obsidian://open?path=" in displayed and "G%C3%A4steliste.md" in displayed
    assert "Guest list" in displayed and "Not uniquely found in Projects" in displayed
    assert "> **Question** Link to" in displayed
    assert "&lt;img" in displayed and "<img src=x" not in displayed
    assert displayed.count("G%C3%A4steliste.md") >= 2  # Properties and body.
    assert note.read_text(encoding="utf-8").startswith("---\nrelated:")


def test_single_differently_named_master_and_vault_link(tmp_path: Path):
    (tmp_path / ".obsidian").mkdir()
    projects = tmp_path / "1-Projects"
    folder = projects / "Pandas Course"
    folder.mkdir(parents=True)
    (folder / "_Pandas Bootcamp.md").write_text("## Notes\nUseful reference", encoding="utf-8")
    (folder / "_Kanban Pandas Course.md").write_text("Board", encoding="utf-8")
    app = create_app(projects)
    panel = render(app, "?view=kanban&project=Pandas+Course")["results"]["children"][0]
    text = str(panel)
    assert "Useful reference" in text
    assert "obsidian://open?vault=" in text and "Pandas%20Bootcamp.md" in text


def test_missing_and_ambiguous_master_do_not_guess(tmp_path: Path):
    folder = tmp_path / "Work"
    folder.mkdir()
    app = create_app(tmp_path)
    missing = render(app, "?view=kanban&project=Work")["results"]["children"]
    assert "No project master note" in str(missing[0])
    assert "No tasks in this project yet" in str(missing[2])
    (folder / "_First.md").write_text("first", encoding="utf-8")
    (folder / "_Second.md").write_text("second", encoding="utf-8")
    ambiguous = render(app, "?view=kanban&project=Work")["results"]["children"][0]
    assert "Several _*.md notes" in str(ambiguous)
    assert "first" not in str(ambiguous) and "second" not in str(ambiguous)


def test_invalid_properties_are_shown_as_text_and_images_do_not_embed(tmp_path: Path):
    folder = tmp_path / "Work"
    folder.mkdir()
    (folder / "_Work.md").write_text(
        "---\nstatus: [unfinished\n---\nNotes ![remote](https://example.org/a.png) "
        "and ![[local.png]]\n",
        encoding="utf-8",
    )
    note = load_project_note(tmp_path, "Work")
    assert note.raw_properties == "status: [unfinished\n"
    assert "Could not parse properties" in note.message
    assert "![" not in note.body
    assert "https://example.org" not in note.body
    assert "local.png" in note.body
    panel = render(create_app(tmp_path), "?view=kanban&project=Work")["results"]["children"][0]
    assert "status: [unfinished" in str(panel)


def test_does_not_read_symlinked_note_or_folder_or_foreign_project(tmp_path: Path):
    folder = tmp_path / "Work"
    folder.mkdir()
    outside = tmp_path / "elsewhere.md"
    outside.write_text("Private", encoding="utf-8")
    (folder / "_Work.md").symlink_to(outside)
    assert load_project_note(tmp_path, "Work").source is None
    (tmp_path / "Alias").symlink_to(folder, target_is_directory=True)
    assert load_project_note(tmp_path, "Alias").source is None
    assert load_project_note(tmp_path, "../Work").source is None


def test_project_note_reads_without_posix_flags_or_dir_fd(tmp_path: Path, monkeypatch):
    folder = tmp_path / "Work"
    folder.mkdir()
    note = folder / "_Work.md"
    note.write_text("# Local context\n", encoding="utf-8")
    with monkeypatch.context() as patch:
        patch.delattr(os, "O_NOFOLLOW", raising=False)
        patch.delattr(os, "O_DIRECTORY", raising=False)
        assert load_project_note(tmp_path, "Work").body == "# Local context\n"
        (tmp_path / "outside.md").write_text("Private", encoding="utf-8")
        note.unlink()
        note.symlink_to(tmp_path / "outside.md")
        assert load_project_note(tmp_path, "Work").source is None


def test_project_note_refreshes_on_next_render_and_not_in_overview(tmp_path: Path):
    folder = tmp_path / "Work"
    folder.mkdir()
    note = folder / "_Work.md"
    note.write_text("First draft", encoding="utf-8")
    app = create_app(tmp_path)
    assert "First draft" not in str(render(app)["results"])
    assert "First draft" in str(render(app, "?view=kanban&project=Work")["results"])
    note.write_text("Revised notes", encoding="utf-8")
    assert "Revised notes" in str(render(app, "?view=kanban&project=Work")["results"])
