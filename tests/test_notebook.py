import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "01_reproducible_smoke_test.ipynb"
PINNED_REVISION = "f67005b294a0e23f7ab820c001e119a4b6e7d29a"
GPU_NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "02_minimum_gpu_training.ipynb"
GPU_PINNED_REVISION = "c4282d2ae1e980b7cebb028ee857b1f4612ca9a5"
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

    def test_scope_is_synthetic_and_persists_to_versioned_drive_folder(self):
        self.assertIn('"uses_real_pothole_data": False', self.sources)
        self.assertIn('"scientific_result": False', self.sources)
        self.assertIn("drive.mount", self.sources)
        self.assertIn(
            "TESIS/experiments/experiment-pilot-v0.1/runs", self.sources
        )
        self.assertIn("persist_experiment_run", self.sources)
        self.assertIn("validate_persisted_run", self.sources)
        self.assertIn('"drive_persistence_confirmed": True', self.sources)
        self.assertEqual(self.sources.count("ArtifactSpec("), 9)

    def test_validates_training_outputs(self):
        for expected_check in (
            "changed_tensor_count > 0",
            "len(epoch_rows) == EPOCHS",
            "best_weights.is_file()",
            "last_weights.is_file()",
            "results_plot.is_file()",
        ):
            self.assertIn(expected_check, self.sources)

    def test_published_copy_contains_a_successful_gpu_execution(self):
        code_cells = [
            cell for cell in self.notebook["cells"] if cell["cell_type"] == "code"
        ]
        if any(cell["execution_count"] is None for cell in code_cells):
            self.skipTest("La ejecución completa requiere GPU y autorización de Drive")
        self.assertEqual(
            [cell["execution_count"] for cell in code_cells],
            list(range(1, len(code_cells) + 1)),
        )
        self.assertFalse(
            any(
                output.get("output_type") == "error"
                for cell in code_cells
                for output in cell["outputs"]
            )
        )

        text_outputs = []
        for cell in code_cells:
            for output in cell["outputs"]:
                text = output.get("text")
                if isinstance(text, list):
                    text_outputs.extend(text)
                elif isinstance(text, str):
                    text_outputs.append(text)
        joined_outputs = "".join(text_outputs)
        for evidence in (
            '"gpu_name": "Tesla T4"',
            '"cuda_training_confirmed": true',
            '"completed_epochs": 2',
            '"status": "passed"',
            '"drive_persistence_confirmed": true',
            '"artifact_count": 9',
        ):
            self.assertIn(evidence, joined_outputs)


if __name__ == "__main__":
    unittest.main()
