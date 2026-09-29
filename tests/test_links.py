from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from marktask.index import parse_markdown
from marktask.links import ObsidianLinks, find_vault_root


def test_core_uri_opens_exact_note_and_encodes_special_characters(tmp_path: Path):
    root = tmp_path / "My Vault" / "1-Projects"
    root.mkdir(parents=True)
    task, _ = parse_markdown("- [ ] Prüfen #work\n", "Überblick & Notes/Plan #1.md", "Überblick & Notes")
    uri, title = ObsidianLinks(root).for_task(task[0])
    assert uri.startswith("obsidian://open?path=")
    assert "%20" in uri and "%23" in uri and "%26" in uri
    assert parse_qs(urlsplit(uri).query)["path"] == [str(root / task[0].source)]
    assert "manual navigation" in title  # Core Obsidian has no arbitrary line parameter.


def test_native_block_link_when_vault_is_known(tmp_path: Path):
    vault = tmp_path / "My Vault"
    (vault / ".obsidian").mkdir(parents=True)
    projects = vault / "1-Projects"
    projects.mkdir()
    task, _ = parse_markdown("- [ ] Deep link ^f177a2", "Project/Note.md", "Project")
    assert find_vault_root(projects) == vault
    uri, title = ObsidianLinks(projects, vault).for_task(task[0])
    params = parse_qs(urlsplit(uri).query)
    assert params == {"vault": ["My Vault"], "file": ["1-Projects/Project/Note.md#^f177a2"]}
    assert "block" in title


def test_advanced_uri_opens_exact_one_indexed_line(tmp_path: Path):
    vault = tmp_path / "My Vault"
    projects = vault / "1-Projects"
    projects.mkdir(parents=True)
    task, _ = parse_markdown("Text\n- [ ] Task\n", "Project/Note.md", "Project")
    uri, title = ObsidianLinks(projects, vault, "vault-id", advanced_uri=True).for_task(task[0])
    assert uri.startswith("obsidian://adv-uri?")
    assert parse_qs(urlsplit(uri).query) == {
        "vault": ["vault-id"], "filepath": ["1-Projects/Project/Note.md"], "line": ["2"],
    }
    assert "line 2" in title


def test_advanced_uri_requires_a_containing_vault(tmp_path: Path):
    projects = tmp_path / "1-Projects"
    projects.mkdir()
    with pytest.raises(ValueError, match="vault root"):
        ObsidianLinks(projects, advanced_uri=True)
    with pytest.raises(ValueError, match="must contain"):
        ObsidianLinks(projects, tmp_path / "elsewhere")


def test_wikilinks_resolve_only_unique_local_markdown_notes(tmp_path: Path):
    root = tmp_path / "1-Projects"
    links = ObsidianLinks(root)
    sources = ("Work/_Work.md", "Work/Gästeliste.md", "Other/Gästeliste.md", "Work/Sub/Plan.md")
    assert parse_qs(urlsplit(links.for_wikilink("Gästeliste", "Work/_Work.md", sources)).query)["path"] == [
        str(root / "Work/Gästeliste.md")]
    assert parse_qs(urlsplit(links.for_wikilink("Sub/Plan#Goal", "Work/_Work.md", sources)).query)["path"] == [
        str(root / "Work/Sub/Plan.md")]
    assert links.for_wikilink("Gästeliste", "Another/_Another.md", sources) is None  # Ambiguous.
    assert links.for_wikilink("../outside", "Work/_Work.md", sources) is None
    assert links.for_wikilink("Missing", "Work/_Work.md", sources) is None
