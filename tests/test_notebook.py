import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "01_reproducible_smoke_test.ipynb"
PINNED_REVISION = "f67005b294a0e23f7ab820c001e119a4b6e7d29a"


def cell_source(cell: dict) -> str:
    source = cell["source"]
    return "".join(source) if isinstance(source, list) else source


class ColabNotebookTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))

    def test_uses_supported_notebook_format_and_python_kernel(self):
        self.assertEqual(self.notebook["nbformat"], 4)
        self.assertEqual(self.notebook["metadata"]["kernelspec"]["name"], "python3")
        self.assertEqual(
            self.notebook["metadata"]["colab"]["name"],
            NOTEBOOK_PATH.name,
        )

    def test_contains_required_tutorial_sections(self):
        markdown = "\n".join(
            cell_source(cell)
            for cell in self.notebook["cells"]
            if cell["cell_type"] == "markdown"
        )
        for heading in ("## Goal", "## Setup", "## Steps", "## Checks", "## Next Steps"):
            self.assertIn(heading, markdown)

    def test_pins_an_exact_repository_revision(self):
        sources = "\n".join(cell_source(cell) for cell in self.notebook["cells"])
        self.assertIn(PINNED_REVISION, sources)
        self.assertNotIn('PROJECT_REVISION = "main"', sources)

    def test_all_code_cells_were_executed_without_errors(self):
        code_cells = [
            cell for cell in self.notebook["cells"] if cell["cell_type"] == "code"
        ]
        self.assertGreaterEqual(len(code_cells), 7)
        for cell in code_cells:
            self.assertIsNotNone(cell["execution_count"])
            self.assertFalse(
                any(output.get("output_type") == "error" for output in cell["outputs"])
            )


if __name__ == "__main__":
    unittest.main()
