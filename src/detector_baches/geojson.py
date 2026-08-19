"""Conversión del contrato de observaciones a GeoJSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from detector_baches.models import Observation

SCHEMA_VERSION = "0.1.0"


def observations_to_feature_collection(
    observations: Iterable[Observation],
) -> dict[str, Any]:
    features = [
        {
            "type": "Feature",
            "id": observation.observation_id,
            "geometry": {
                "type": "Point",
                "coordinates": [observation.longitude, observation.latitude],
            },
            "properties": observation.properties(),
        }
        for observation in observations
    ]
    return {
        "type": "FeatureCollection",
        "schema_version": SCHEMA_VERSION,
        "features": features,
    }


def load_observations(path: Path) -> list[Observation]:
    with path.open("r", encoding="utf-8") as source:
        payload = json.load(source)

    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"schema_version debe ser {SCHEMA_VERSION}; "
            f"se recibió {payload.get('schema_version')!r}"
        )
    values = payload.get("observations")
    if not isinstance(values, list):
        raise ValueError("observations debe ser una lista")
    return [Observation.from_mapping(value) for value in values]


def convert_observations_file(input_path: Path, output_path: Path) -> int:
    observations = load_observations(input_path)
    feature_collection = observations_to_feature_collection(observations)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as destination:
        json.dump(feature_collection, destination, ensure_ascii=False, indent=2)
        destination.write("\n")
    return len(observations)
