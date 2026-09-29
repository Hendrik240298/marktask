import importlib.util
from pathlib import Path
import sys

import pytest


def load_initializer():
    path = Path(__file__).parent.parent / "scripts" / "init_venv.py"
    spec = importlib.util.spec_from_file_location("marktask_init_venv", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_initializer_creates_local_environment_and_installs_checkout(tmp_path, monkeypatch):
    module = load_initializer()
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    monkeypatch.setattr(module, "__file__", str(scripts / "init_venv.py"))
    monkeypatch.setattr(sys, "argv", ["init_venv.py"])
    created = []
    installed = []

    def fake_create(path, with_pip):
        created.append((path, with_pip))
        path.mkdir()
        (path / "pyvenv.cfg").write_text("home = synthetic\n", encoding="utf-8")

    monkeypatch.setattr(module.venv, "create", fake_create)
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: installed.append((args, kwargs)))
    module.main()

    environment = tmp_path / ".venv"
    executable = environment / ("Scripts/python.exe" if module.os.name == "nt" else "bin/python")
    assert created == [(environment, True)]
    assert installed == [(([str(executable), "-m", "pip", "install", "-e", "."],),
                          {"cwd": tmp_path, "check": True})]

    monkeypatch.setattr(sys, "argv", ["init_venv.py", "--dev"])
    module.main()
    assert len(created) == 1
    assert installed[-1][0][0][-1] == ".[dev]"


def test_initializer_refuses_to_write_into_nonvenv(tmp_path, monkeypatch):
    module = load_initializer()
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    monkeypatch.setattr(module, "__file__", str(scripts / "init_venv.py"))
    monkeypatch.setattr(sys, "argv", ["init_venv.py"])
    (tmp_path / ".venv").mkdir()
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: pytest.fail("pip must not run"))
    with pytest.raises(SystemExit, match="2"):
        module.main()


def test_initializer_refuses_symlinked_environment(tmp_path, monkeypatch):
    module = load_initializer()
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    monkeypatch.setattr(module, "__file__", str(scripts / "init_venv.py"))
    monkeypatch.setattr(sys, "argv", ["init_venv.py"])
    target = tmp_path / "other"
    target.mkdir()
    (tmp_path / ".venv").symlink_to(target, target_is_directory=True)
    with pytest.raises(SystemExit, match="2"):
        module.main()
