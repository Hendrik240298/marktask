"""Set up a local Python environment without requiring uv or pyenv."""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import venv


def main() -> None:
    parser = argparse.ArgumentParser(description="Create .venv and install this MarkTask checkout")
    parser.add_argument("--dev", action="store_true", help="Also install test dependencies")
    args = parser.parse_args()

    if sys.version_info < (3, 11):
        parser.error("MarkTask requires Python 3.11 or newer")

    root = Path(__file__).absolute().parent.parent
    environment = root / ".venv"
    if environment.is_symlink() or (environment.exists() and not (environment / "pyvenv.cfg").is_file()):
        parser.error(".venv exists but is not a regular Python environment; leave it untouched and inspect it")

    if not environment.exists():
        venv.create(environment, with_pip=True)

    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run([str(python), "-m", "pip", "install", "-e", ".[dev]" if args.dev else "."],
                   cwd=root, check=True)
    print(f"MarkTask is ready. Use {python} -m marktask.cli serve --projects-dir PATH")


if __name__ == "__main__":
    main()
