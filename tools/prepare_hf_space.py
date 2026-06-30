from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".hf-space-build"

COPY_ITEMS = [
    "data",
    "src",
    "static",
    "Dockerfile",
    "requirements-space.txt",
]


def copy_item(name: str) -> None:
    source = ROOT / name
    target = OUT / name
    if source.is_dir():
        shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "weather"))
    else:
        shutil.copy2(source, target)


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    for item in COPY_ITEMS:
        copy_item(item)
    shutil.copy2(ROOT / "README.hf.md", OUT / "README.md")
    print(OUT)


if __name__ == "__main__":
    main()
