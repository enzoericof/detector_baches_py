import json
import tempfile
import unittest
from pathlib import Path

from detector_baches.geojson import (
    convert_observations_file,
    observations_to_feature_collection,
)
from detector_baches.models import Observation


def valid_observation(**changes):
    values = {
        "observation_id": "obs-001",
        "trip_id": "trip-001",
        "track_id": "track-001",
        "started_at_ms": 1000,
        "ended_at_ms": 2000,
        "detection_count": 3,
        "confidence_max": 0.9,
        "confidence_mean": 0.8,
        "latitude": -25.29,
        "longitude": -57.63,
        "horizontal_accuracy_m": 5.0,
        "model_version": "simulated-test",
        "speed_mps": 10.0,
        "heading_deg": 180.0,
    }
    values.update(changes)
    return Observation(**values)


class ObservationTest(unittest.TestCase):
    def test_rejects_invalid_coordinates(self):
        with self.assertRaisesRegex(ValueError, "latitude"):
            valid_observation(latitude=-100.0)

    def test_rejects_invalid_time_interval(self):
        with self.assertRaisesRegex(ValueError, "intervalo temporal"):
            valid_observation(started_at_ms=2000, ended_at_ms=1000)


class GeoJsonTest(unittest.TestCase):
    def test_uses_geojson_coordinate_order(self):
        collection = observations_to_feature_collection([valid_observation()])

        self.assertEqual(collection["type"], "FeatureCollection")
        self.assertEqual(
            collection["features"][0]["geometry"]["coordinates"],
            [-57.63, -25.29],
        )

    def test_converts_a_versioned_file(self):
        payload = {
            "schema_version": "0.1.0",
            "observations": [
                {
                    "observation_id": "obs-001",
                    "trip_id": "trip-001",
                    "track_id": "track-001",
                    "started_at_ms": 1000,
                    "ended_at_ms": 2000,
                    "detection_count": 3,
                    "confidence_max": 0.9,
                    "confidence_mean": 0.8,
                    "latitude": -25.29,
                    "longitude": -57.63,
                    "horizontal_accuracy_m": 5.0,
                    "model_version": "simulated-test"
                }
            ],
        }

        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "observations.json"
            output_path = Path(directory) / "map" / "observations.geojson"
            input_path.write_text(json.dumps(payload), encoding="utf-8")

            count = convert_observations_file(input_path, output_path)
            result = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(count, 1)
        self.assertEqual(result["features"][0]["id"], "obs-001")


if __name__ == "__main__":
    unittest.main()
