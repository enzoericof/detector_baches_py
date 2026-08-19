"""Ejecuta un notebook de principio a fin y conserva sus salidas."""

from __future__ import annotations

import argparse
from pathlib import Path

import nbformat
from nbclient import NotebookClient


def execute_notebook(path: Path) -> None:
    notebook = nbformat.read(path, as_version=4)
    client = NotebookClient(
        notebook,
        timeout=600,
        kernel_name="python3",
        resources={"metadata": {"path": str(path.parent.resolve())}},
    )
    client.execute()
    nbformat.write(notebook, path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ejecuta un notebook y guarda sus salidas verificadas."
    )
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    execute_notebook(args.path)
    print(f"Notebook ejecutado correctamente: {args.path}")


if __name__ == "__main__":
    main()
