import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from detector_baches.dataset_validation import (
    DatasetValidationError,
    validate_dataset_directory,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ROOT = PROJECT_ROOT / "examples" / "dataset-local-v0.1"


def copy_example(destination: Path) -> Path:
    target = destination / EXAMPLE_ROOT.name
    shutil.copytree(EXAMPLE_ROOT, target)
    return target


def read_manifest(root: Path) -> dict:
    return json.loads((root / "manifest.json").read_text(encoding="utf-8"))


def write_manifest(root: Path, manifest: dict) -> None:
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_samples(root: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in (root / "samples.jsonl").read_text(encoding="utf-8").splitlines()
    ]


def write_samples_and_refresh_hash(root: Path, records: list[dict]) -> None:
    index_path = root / "samples.jsonl"
    index_path.write_text(
        "\n".join(
            json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            for record in records
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = read_manifest(root)
    manifest["files"]["sample_index"]["sha256"] = hashlib.sha256(
        index_path.read_bytes()
    ).hexdigest()
    write_manifest(root, manifest)


class DatasetValidationTest(unittest.TestCase):
    def test_validates_versioned_example_without_artifacts(self):
        report = validate_dataset_directory(EXAMPLE_ROOT, require_artifacts=False)

        self.assertEqual(report.dataset_id, "dataset-local-v0.1")
        self.assertEqual(report.sample_count, 6)
        self.assertEqual(report.positive_sample_count, 4)
        self.assertEqual(report.negative_sample_count, 2)
        self.assertEqual(report.annotation_count, 5)

    def test_requires_images_and_labels_by_default(self):
        with self.assertRaisesRegex(DatasetValidationError, "falta el artefacto"):
            validate_dataset_directory(EXAMPLE_ROOT)

    def test_accepts_all_artifacts_when_hashes_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = copy_example(Path(directory))
            records = read_samples(root)
            for record in records:
                image_path = root.joinpath(*Path(record["image"]["relative_path"]).parts)
                label_path = root.joinpath(*Path(record["annotation"]["relative_path"]).parts)
                image_path.parent.mkdir(parents=True, exist_ok=True)
                label_path.parent.mkdir(parents=True, exist_ok=True)
                image_path.write_bytes(f"image-{record['sample_id']}".encode())
                if record["is_negative"]:
                    label_path.write_bytes(b"")
                else:
                    label_path.write_bytes(
                        ("0 0.5 0.5 0.2 0.2\n" * record["annotation"]["object_count"]).encode()
                    )
                record["image"]["sha256"] = hashlib.sha256(image_path.read_bytes()).hexdigest()
                record["annotation"]["sha256"] = hashlib.sha256(
                    label_path.read_bytes()
                ).hexdigest()
            write_samples_and_refresh_hash(root, records)

            report = validate_dataset_directory(root)

        self.assertEqual(report.annotation_count, 5)

    def test_rejects_trip_assigned_to_two_splits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = copy_example(Path(directory))
            manifest = read_manifest(root)
            manifest["splits"][1]["trip_ids"].append(
                "trip-20260819-0705-R01-P01"
            )
            write_manifest(root, manifest)

            with self.assertRaisesRegex(DatasetValidationError, "fuga de partición"):
                validate_dataset_directory(root, require_artifacts=False)

    def test_rejects_sample_in_wrong_split(self):
        with tempfile.TemporaryDirectory() as directory:
            root = copy_example(Path(directory))
            records = read_samples(root)
            records[0]["split"] = "validation"
            records[0]["image"]["relative_path"] = "images/validation/sample-000001.jpg"
            records[0]["annotation"]["relative_path"] = (
                "labels/validation/sample-000001.txt"
            )
            write_samples_and_refresh_hash(root, records)

            with self.assertRaisesRegex(DatasetValidationError, "manifiesto indica"):
                validate_dataset_directory(root, require_artifacts=False)

    def test_rejects_incorrect_statistics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = copy_example(Path(directory))
            manifest = read_manifest(root)
            manifest["statistics"]["sample_count"] = 7
            write_manifest(root, manifest)

            with self.assertRaisesRegex(DatasetValidationError, "sample_count debe ser 6"):
                validate_dataset_directory(root, require_artifacts=False)

    def test_rejects_modified_sample_index(self):
        with tempfile.TemporaryDirectory() as directory:
            root = copy_example(Path(directory))
            manifest = read_manifest(root)
            manifest["files"]["sample_index"]["sha256"] = "0" * 64
            write_manifest(root, manifest)

            with self.assertRaisesRegex(DatasetValidationError, "sha256 no coincide"):
                validate_dataset_directory(root, require_artifacts=False)

    def test_rejects_negative_sample_with_objects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = copy_example(Path(directory))
            records = read_samples(root)
            records[1]["annotation"]["object_count"] = 1
            records[1]["annotation"]["class_counts"]["pothole"] = 1
            write_samples_and_refresh_hash(root, records)

            with self.assertRaisesRegex(DatasetValidationError, "es negativo"):
                validate_dataset_directory(root, require_artifacts=False)

    def test_frozen_dataset_requires_reviews_and_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = copy_example(Path(directory))
            manifest = read_manifest(root)
            manifest["status"] = "frozen"
            manifest["frozen_at_utc"] = "2026-08-19T15:00:00.000Z"
            manifest["code_revision"] = "8cdeee9"
            write_manifest(root, manifest)

            with self.assertRaisesRegex(DatasetValidationError, "dataset frozen"):
                validate_dataset_directory(root, require_artifacts=False)

    def test_dataset_schemas_are_valid_json(self):
        for name in ("dataset_manifest.schema.json", "dataset_sample.schema.json"):
            schema = json.loads(
                (PROJECT_ROOT / "schemas" / name).read_text(encoding="utf-8")
            )
            self.assertEqual(
                schema["$schema"],
                "https://json-schema.org/draft/2020-12/schema",
            )


if __name__ == "__main__":
    unittest.main()
