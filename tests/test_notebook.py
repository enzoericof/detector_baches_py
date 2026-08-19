import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "01_reproducible_smoke_test.ipynb"
PINNED_REVISION = "f67005b294a0e23f7ab820c001e119a4b6e7d29a"
GPU_NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "02_minimum_gpu_training.ipynb"
GPU_PINNED_REVISION = "45cb8f28ad2b00698a33cbcca756685648bde8fa"
PINNED_ULTRALYTICS_VERSION = "8.4.123"


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


class MinimumGpuTrainingNotebookTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.notebook = json.loads(GPU_NOTEBOOK_PATH.read_text(encoding="utf-8"))
        cls.sources = "\n".join(
            cell_source(cell) for cell in cls.notebook["cells"]
        )

    def test_requests_a_gpu_and_uses_the_python_kernel(self):
        self.assertEqual(self.notebook["metadata"]["accelerator"], "GPU")
        self.assertEqual(self.notebook["metadata"]["kernelspec"]["name"], "python3")
        self.assertEqual(
            self.notebook["metadata"]["colab"]["name"],
            GPU_NOTEBOOK_PATH.name,
        )

    def test_contains_required_tutorial_sections(self):
        markdown = "\n".join(
            cell_source(cell)
            for cell in self.notebook["cells"]
            if cell["cell_type"] == "markdown"
        )
        for heading in ("## Goal", "## Setup", "## Steps", "## Checks", "## Next Steps"):
            self.assertIn(heading, markdown)

    def test_pins_code_dependency_and_training_parameters(self):
        self.assertIn(GPU_PINNED_REVISION, self.sources)
        self.assertIn(
            f'ULTRALYTICS_VERSION = "{PINNED_ULTRALYTICS_VERSION}"',
            self.sources,
        )
        self.assertIn("EPOCHS = 2", self.sources)
        self.assertIn("BATCH_SIZE = 4", self.sources)
        self.assertIn('model = YOLO("yolo26n.yaml")', self.sources)

    def test_requires_cuda_without_cpu_fallback(self):
        self.assertIn("if not torch.cuda.is_available()", self.sources)
        self.assertIn("device=0", self.sources)
        self.assertIn('training_device_evidence.get("is_cuda") is True', self.sources)

    def test_scope_is_synthetic_and_drive_is_deferred(self):
        self.assertIn('"uses_real_pothole_data": False', self.sources)
        self.assertIn('"scientific_result": False', self.sources)
        self.assertNotIn("drive.mount", self.sources)

    def test_validates_training_outputs(self):
        for expected_check in (
            "changed_tensor_count > 0",
            "len(epoch_rows) == EPOCHS",
            "best_weights.is_file()",
            "last_weights.is_file()",
            "results_plot.is_file()",
        ):
            self.assertIn(expected_check, self.sources)


if __name__ == "__main__":
    unittest.main()
