"""Modelos de dominio estables para comunicar las fases del sistema."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} debe ser numérico")
    number = float(value)
    if not isfinite(number):
        raise ValueError(f"{field} debe ser finito")
    return number


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} no puede estar vacío")
    return value.strip()


@dataclass(frozen=True, slots=True)
class Observation:
    """Un bache observado una vez durante un viaje."""

    observation_id: str
    trip_id: str
    track_id: str
    started_at_ms: int
    ended_at_ms: int
    detection_count: int
    confidence_max: float
    confidence_mean: float
    latitude: float
    longitude: float
    horizontal_accuracy_m: float
    model_version: str
    speed_mps: float | None = None
    heading_deg: float | None = None
    road_segment_id: str | None = None
    evidence_uri: str | None = None

    def __post_init__(self) -> None:
        for field in ("observation_id", "trip_id", "track_id", "model_version"):
            _required_text(getattr(self, field), field)

        if self.started_at_ms < 0 or self.ended_at_ms < self.started_at_ms:
            raise ValueError("el intervalo temporal de la observación no es válido")
        if self.detection_count <= 0:
            raise ValueError("detection_count debe ser mayor que cero")

        if not 0 <= _finite_number(self.confidence_max, "confidence_max") <= 1:
            raise ValueError("confidence_max debe estar entre 0 y 1")
        if not 0 <= _finite_number(self.confidence_mean, "confidence_mean") <= 1:
            raise ValueError("confidence_mean debe estar entre 0 y 1")
        if self.confidence_mean > self.confidence_max:
            raise ValueError("confidence_mean no puede superar confidence_max")

        if not -90 <= _finite_number(self.latitude, "latitude") <= 90:
            raise ValueError("latitude debe estar entre -90 y 90")
        if not -180 <= _finite_number(self.longitude, "longitude") <= 180:
            raise ValueError("longitude debe estar entre -180 y 180")
        if _finite_number(self.horizontal_accuracy_m, "horizontal_accuracy_m") < 0:
            raise ValueError("horizontal_accuracy_m no puede ser negativa")

        if self.speed_mps is not None and _finite_number(self.speed_mps, "speed_mps") < 0:
            raise ValueError("speed_mps no puede ser negativa")
        if self.heading_deg is not None:
            heading = _finite_number(self.heading_deg, "heading_deg")
            if not 0 <= heading < 360:
                raise ValueError("heading_deg debe estar entre 0 y 360")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "Observation":
        """Construye y valida una observación a partir de JSON."""

        required = {
            "observation_id",
            "trip_id",
            "track_id",
            "started_at_ms",
            "ended_at_ms",
            "detection_count",
            "confidence_max",
            "confidence_mean",
            "latitude",
            "longitude",
            "horizontal_accuracy_m",
            "model_version",
        }
        missing = sorted(required.difference(value))
        if missing:
            raise ValueError(f"faltan campos requeridos: {', '.join(missing)}")

        return cls(
            observation_id=value["observation_id"],
            trip_id=value["trip_id"],
            track_id=value["track_id"],
            started_at_ms=value["started_at_ms"],
            ended_at_ms=value["ended_at_ms"],
            detection_count=value["detection_count"],
            confidence_max=value["confidence_max"],
            confidence_mean=value["confidence_mean"],
            latitude=value["latitude"],
            longitude=value["longitude"],
            horizontal_accuracy_m=value["horizontal_accuracy_m"],
            model_version=value["model_version"],
            speed_mps=value.get("speed_mps"),
            heading_deg=value.get("heading_deg"),
            road_segment_id=value.get("road_segment_id"),
            evidence_uri=value.get("evidence_uri"),
        )

    def properties(self) -> dict[str, Any]:
        """Devuelve atributos no geométricos para una entidad GeoJSON."""

        return {
            "observation_id": self.observation_id,
            "trip_id": self.trip_id,
            "track_id": self.track_id,
            "started_at_ms": self.started_at_ms,
            "ended_at_ms": self.ended_at_ms,
            "detection_count": self.detection_count,
            "confidence_max": self.confidence_max,
            "confidence_mean": self.confidence_mean,
            "horizontal_accuracy_m": self.horizontal_accuracy_m,
            "model_version": self.model_version,
            "speed_mps": self.speed_mps,
            "heading_deg": self.heading_deg,
            "road_segment_id": self.road_segment_id,
            "evidence_uri": self.evidence_uri,
        }
