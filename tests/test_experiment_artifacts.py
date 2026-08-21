import json
import tempfile
import unittest
from pathlib import Path

from detector_baches.experiment_artifacts import (
    ArtifactPersistenceError,
    ArtifactSpec,
    persist_experiment_run,
    validate_persisted_run,
)


class ExperimentArtifactPersistenceTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.source = self.root / "source"
        self.destination = self.root / "drive" / "runs"
        (self.source / "weights").mkdir(parents=True)
        (self.source / "weights" / "best.pt").write_bytes(b"model-weights")
        (self.source / "results.csv").write_text(
            "epoch,loss\n1,1.5\n", encoding="utf-8"
        )
        self.specs = [
            ArtifactSpec(
                source_path="weights/best.pt",
                destination_path="weights/best.pt",
                role="best_weights",
                media_type="application/octet-stream",
            ),
            ArtifactSpec(
                source_path="results.csv",
                destination_path="metrics/results.csv",
                role="epoch_metrics",
                media_type="text/csv",
            ),
        ]
        self.metadata = {
            "created_at_utc": "2026-08-21T15:30:00Z",
            "project_revision": "9cc6210",
            "scientific_result": False,
        }

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_persists_and_validates_a_complete_run(self):
        report = persist_experiment_run(
            self.source,
            self.destination,
            "task10-test-20260821t153000z-9cc6210",
            self.specs,
            self.metadata,
        )

        self.assertEqual(report.artifact_count, 2)
        self.assertGreater(report.total_bytes, 0)
        self.assertFalse(report.reused_existing_run)
        self.assertTrue((report.run_directory / "_SUCCESS.json").is_file())
        self.assertTrue(
            (report.run_directory / "weights" / "best.pt").is_file()
        )
        self.assertTrue(
            (report.run_directory / "metrics" / "results.csv").is_file()
        )

        manifest = json.loads(
            (report.run_directory / "artifact_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["artifact_count"], 2)
        self.assertEqual(
            [artifact["path"] for artifact in manifest["artifacts"]],
            ["metrics/results.csv", "weights/best.pt"],
        )

    def test_completed_run_is_idempotent(self):
        first = persist_experiment_run(
            self.source,
            self.destination,
            "task10-test-20260821t153000z-9cc6210",
            self.specs,
            self.metadata,
        )
        second = persist_experiment_run(
            self.source,
            self.destination,
            "task10-test-20260821t153000z-9cc6210",
            self.specs,
            self.metadata,
        )

        self.assertEqual(first.manifest_sha256, second.manifest_sha256)
        self.assertTrue(second.reused_existing_run)

    def test_rejects_modified_persisted_artifact(self):
        report = persist_experiment_run(
            self.source,
            self.destination,
            "task10-test-20260821t153000z-9cc6210",
            self.specs,
            self.metadata,
        )
        (report.run_directory / "weights" / "best.pt").write_bytes(b"tampered")

        with self.assertRaisesRegex(
            ArtifactPersistenceError, "tamaño|SHA-256"
        ):
            validate_persisted_run(report.run_directory)

    def test_rejects_unsafe_or_duplicate_paths(self):
        with self.assertRaisesRegex(ArtifactPersistenceError, "ruta relativa"):
            persist_experiment_run(
                self.source,
                self.destination,
                "task10-test-20260821t153000z-9cc6210",
                [
                    ArtifactSpec(
                        source_path="../secret.txt",
                        destination_path="secret.txt",
                        role="unsafe",
                        media_type="text/plain",
                    )
                ],
                self.metadata,
            )

        duplicate_specs = [self.specs[0], self.specs[0]]
        with self.assertRaisesRegex(ArtifactPersistenceError, "Destino duplicado"):
            persist_experiment_run(
                self.source,
                self.destination,
                "task10-test-20260821t153001z-9cc6210",
                duplicate_specs,
                self.metadata,
            )

    def test_manifest_schema_is_valid_json(self):
        schema_path = (
            Path(__file__).resolve().parents[1]
            / "schemas"
            / "experiment_artifact_manifest.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["schema_version"]["const"], "0.1.0")


if __name__ == "__main__":
    unittest.main()
