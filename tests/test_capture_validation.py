import json
import shutil
import tempfile
import unittest
from pathlib import Path

from detector_baches.capture_validation import (
    CaptureValidationError,
    validate_capture_directory,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ROOT = PROJECT_ROOT / "examples" / "session-20260819-0700-D01"
TRIP_ID = "trip-20260819-0705-R01-P01"


def copy_example(destination: Path) -> Path:
    target = destination / EXAMPLE_ROOT.name
    shutil.copytree(EXAMPLE_ROOT, target)
    return target


def trip_root(capture_root: Path) -> Path:
    return capture_root / "trips" / TRIP_ID


class CaptureValidationTest(unittest.TestCase):
    def test_validates_versioned_example_without_binary_media(self):
        report = validate_capture_directory(EXAMPLE_ROOT, require_media_files=False)

        self.assertEqual(report.session_id, "session-20260819-0700-D01")
        self.assertEqual(report.trip_count, 1)
        self.assertEqual(report.video_segment_count, 2)
        self.assertEqual(report.gnss_sample_count, 6)
        self.assertEqual(report.event_count, 8)

    def test_requires_declared_video_files_by_default(self):
        with self.assertRaisesRegex(CaptureValidationError, "falta el segmento de video"):
            validate_capture_directory(EXAMPLE_ROOT)

    def test_accepts_complete_capture_with_all_video_segments(self):
        with tempfile.TemporaryDirectory() as directory:
            root = copy_example(Path(directory))
            video_root = trip_root(root) / "video"
            video_root.mkdir()
            for index in (1, 2):
                media = video_root / f"{TRIP_ID}_video_{index:04d}.mp4"
                media.write_bytes(b"synthetic-media-placeholder")

            report = validate_capture_directory(root)

        self.assertEqual(report.video_segment_count, 2)

    def test_rejects_heading_outside_range(self):
        with tempfile.TemporaryDirectory() as directory:
            root = copy_example(Path(directory))
            gnss_path = trip_root(root) / "gnss.jsonl"
            records = [json.loads(line) for line in gnss_path.read_text().splitlines()]
            records[1]["heading_deg"] = 360.0
            gnss_path.write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(CaptureValidationError, "heading_deg"):
                validate_capture_directory(root, require_media_files=False)

    def test_rejects_timestamp_that_disagrees_with_common_clock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = copy_example(Path(directory))
            events_path = trip_root(root) / "events.jsonl"
            records = [json.loads(line) for line in events_path.read_text().splitlines()]
            records[3]["utc_time"] = "2026-08-19T10:13:00.000Z"
            events_path.write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(CaptureValidationError, "reloj común"):
                validate_capture_directory(root, require_media_files=False)

    def test_rejects_gnss_that_ends_before_the_video(self):
        with tempfile.TemporaryDirectory() as directory:
            root = copy_example(Path(directory))
            metadata_path = trip_root(root) / "trip_metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["gnss"]["sample_count"] = 5
            metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

            gnss_path = trip_root(root) / "gnss.jsonl"
            records = gnss_path.read_text(encoding="utf-8").splitlines()[:-1]
            gnss_path.write_text("\n".join(records) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(CaptureValidationError, "último cuadro"):
                validate_capture_directory(root, require_media_files=False)

    def test_accepts_recoverable_interrupted_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = copy_example(Path(directory))
            session_path = root / "session_metadata.json"
            session = json.loads(session_path.read_text(encoding="utf-8"))
            session["status"] = "interrupted"
            session["ended_at_utc"] = None
            session_path.write_text(json.dumps(session, indent=2), encoding="utf-8")

            metadata_path = trip_root(root) / "trip_metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["status"] = "interrupted"
            metadata["ended_at_utc"] = None
            metadata["ended_elapsed_realtime_ns"] = None
            metadata["video"]["segments"][1]["status"] = "partial"
            metadata["video"]["segments"][1]["last_frame_elapsed_realtime_ns"] = None
            metadata["video"]["segments"][1]["last_frame_media_time_us"] = None
            metadata["events"]["event_count"] = 7
            metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

            events_path = trip_root(root) / "events.jsonl"
            records = [json.loads(line) for line in events_path.read_text().splitlines()]
            records = records[:6]
            records.append(
                {
                    "schema_version": "0.1.0",
                    "session_id": root.name,
                    "trip_id": TRIP_ID,
                    "event_id": "event-000007",
                    "event_type": "interruption_detected",
                    "clock_epoch_id": "clock-boot-A1",
                    "utc_time": "2026-08-19T10:15:00.000Z",
                    "elapsed_realtime_ns": 1000000000000,
                }
            )
            events_path.write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )

            report = validate_capture_directory(root, require_media_files=False)

        self.assertEqual(report.event_count, 7)

    def test_capture_schemas_are_valid_json(self):
        for name in (
            "capture_session.schema.json",
            "capture_trip.schema.json",
            "gnss_sample.schema.json",
            "capture_event.schema.json",
        ):
            schema = json.loads((PROJECT_ROOT / "schemas" / name).read_text(encoding="utf-8"))
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
