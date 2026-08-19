"""Validación conjunta de una jornada de captura sincronizada."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import isfinite
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "0.1.0"
SESSION_ID_PATTERN = re.compile(
    r"^session-[0-9]{8}-[0-9]{4}-[A-Za-z0-9][A-Za-z0-9_-]*$"
)
TRIP_ID_PATTERN = re.compile(r"^trip-[0-9]{8}-[0-9]{4}-R[0-9]{2}-P[0-9]{2}$")
EVENT_TYPES = {
    "trip_started",
    "video_segment_started",
    "video_segment_ended",
    "pause_started",
    "pause_ended",
    "interruption_detected",
    "capture_recovered",
    "trip_completed",
}
GNSS_REQUIRED_FIELDS = {
    "schema_version",
    "session_id",
    "trip_id",
    "sample_id",
    "clock_epoch_id",
    "utc_time",
    "elapsed_realtime_ns",
    "latitude",
    "longitude",
    "horizontal_accuracy_m",
    "speed_mps",
    "heading_deg",
    "provider",
}
EVENT_REQUIRED_FIELDS = {
    "schema_version",
    "session_id",
    "trip_id",
    "event_id",
    "event_type",
    "clock_epoch_id",
    "utc_time",
    "elapsed_realtime_ns",
}
MAX_CLOCK_ERROR_SECONDS = 2.0


class CaptureValidationError(ValueError):
    """Agrupa todos los problemas encontrados en una captura."""

    def __init__(self, errors: Sequence[str]) -> None:
        self.errors = tuple(errors)
        detail = "\n".join(f"- {error}" for error in self.errors)
        super().__init__(f"captura inválida:\n{detail}")


@dataclass(frozen=True, slots=True)
class CaptureValidationReport:
    """Resumen de una jornada validada."""

    session_id: str
    trip_count: int
    video_segment_count: int
    gnss_sample_count: int
    event_count: int


def _load_json(path: Path, errors: list[str]) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"falta {path}")
        return {}
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"no se pudo leer {path}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path} debe contener un objeto JSON")
        return {}
    return value


def _load_jsonl(path: Path, errors: list[str]) -> list[Mapping[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        errors.append(f"falta {path}")
        return []
    except (OSError, UnicodeError) as exc:
        errors.append(f"no se pudo leer {path}: {exc}")
        return []

    records: list[Mapping[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            errors.append(f"{path}:{line_number} no puede ser una línea vacía")
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path}:{line_number} no es JSON válido: {exc.msg}")
            continue
        if not isinstance(value, dict):
            errors.append(f"{path}:{line_number} debe contener un objeto JSON")
            continue
        records.append(value)
    return records


def _required_text(
    value: Any, field: str, errors: list[str], pattern: re.Pattern[str] | None = None
) -> str | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} debe ser texto no vacío")
        return None
    if pattern is not None and pattern.fullmatch(value) is None:
        errors.append(f"{field} tiene un formato inválido: {value!r}")
        return None
    return value


def _require_fields(
    value: Mapping[str, Any], required: set[str], prefix: str, errors: list[str]
) -> None:
    missing = sorted(required.difference(value))
    if missing:
        errors.append(f"{prefix} omite campos requeridos: {', '.join(missing)}")


def _integer(value: Any, field: str, errors: list[str], minimum: int = 0) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        errors.append(f"{field} debe ser un entero")
        return None
    if value < minimum:
        errors.append(f"{field} no puede ser menor que {minimum}")
        return None
    return value


def _number(value: Any, field: str, errors: list[str]) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append(f"{field} debe ser numérico")
        return None
    number = float(value)
    if not isfinite(number):
        errors.append(f"{field} debe ser finito")
        return None
    return number


def _utc(value: Any, field: str, errors: list[str]) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        errors.append(f"{field} debe estar en UTC y terminar en Z")
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        errors.append(f"{field} no es una fecha RFC 3339 válida")
        return None
    if parsed.utcoffset() != timedelta(0):
        errors.append(f"{field} debe estar en UTC")
        return None
    return parsed.astimezone(timezone.utc)


def _relative_path(value: Any, field: str, errors: list[str]) -> PurePosixPath | None:
    text = _required_text(value, field, errors)
    if text is None:
        return None
    path = PurePosixPath(text)
    if "\\" in text or path.is_absolute() or ".." in path.parts or path.as_posix() != text:
        errors.append(f"{field} debe ser una ruta relativa segura con separadores /")
        return None
    return path


def _estimate_utc(
    points: Sequence[tuple[int, datetime]], elapsed_realtime_ns: int
) -> datetime | None:
    if not points:
        return None
    if len(points) == 1:
        anchor_ns, anchor_utc = points[0]
        return anchor_utc + timedelta(seconds=(elapsed_realtime_ns - anchor_ns) / 1e9)

    left, right = points[0], points[1]
    for candidate_left, candidate_right in zip(points, points[1:]):
        left, right = candidate_left, candidate_right
        if candidate_left[0] <= elapsed_realtime_ns <= candidate_right[0]:
            break
        if elapsed_realtime_ns < candidate_left[0]:
            break

    elapsed_span = right[0] - left[0]
    if elapsed_span <= 0:
        return None
    ratio = (elapsed_realtime_ns - left[0]) / elapsed_span
    utc_span = (right[1] - left[1]).total_seconds()
    return left[1] + timedelta(seconds=utc_span * ratio)


def _check_clock_alignment(
    declared_utc: datetime | None,
    elapsed_realtime_ns: int | None,
    points: Sequence[tuple[int, datetime]],
    field: str,
    errors: list[str],
) -> None:
    if declared_utc is None or elapsed_realtime_ns is None:
        return
    estimated = _estimate_utc(points, elapsed_realtime_ns)
    if estimated is None:
        errors.append(f"{field} no se puede relacionar con UTC")
        return
    difference = abs((declared_utc - estimated).total_seconds())
    if difference > MAX_CLOCK_ERROR_SECONDS:
        errors.append(
            f"{field} difiere {difference:.3f} s del reloj común "
            f"(máximo {MAX_CLOCK_ERROR_SECONDS:.1f} s)"
        )


def _validate_session(
    root: Path, session: Mapping[str, Any], errors: list[str]
) -> tuple[str | None, dict[str, list[tuple[int, datetime]]], list[str]]:
    if session.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"session_metadata.schema_version debe ser {SCHEMA_VERSION}")

    session_id = _required_text(
        session.get("session_id"), "session_metadata.session_id", errors, SESSION_ID_PATTERN
    )
    if session_id is not None and root.name != session_id:
        errors.append(
            f"la carpeta de jornada debe llamarse {session_id!r}, no {root.name!r}"
        )

    _required_text(session.get("device_id"), "session_metadata.device_id", errors)
    _required_text(session.get("vehicle_id"), "session_metadata.vehicle_id", errors)
    _required_text(session.get("timezone"), "session_metadata.timezone", errors)

    status = session.get("status")
    if status not in {"active", "completed", "interrupted"}:
        errors.append("session_metadata.status debe ser active, completed o interrupted")

    started_utc = _utc(session.get("started_at_utc"), "session_metadata.started_at_utc", errors)
    ended_value = session.get("ended_at_utc")
    ended_utc = (
        None
        if ended_value is None
        else _utc(ended_value, "session_metadata.ended_at_utc", errors)
    )
    if status == "completed" and ended_utc is None:
        errors.append("una jornada completed debe tener ended_at_utc")
    if started_utc is not None and ended_utc is not None and ended_utc < started_utc:
        errors.append("session_metadata.ended_at_utc no puede preceder started_at_utc")

    epoch_points: dict[str, list[tuple[int, datetime]]] = {}
    epochs = session.get("clock_epochs")
    if not isinstance(epochs, list) or not epochs:
        errors.append("session_metadata.clock_epochs debe contener al menos una época")
        epochs = []
    for epoch_index, epoch in enumerate(epochs):
        prefix = f"session_metadata.clock_epochs[{epoch_index}]"
        if not isinstance(epoch, dict):
            errors.append(f"{prefix} debe ser un objeto")
            continue
        epoch_id = _required_text(epoch.get("clock_epoch_id"), f"{prefix}.clock_epoch_id", errors)
        if epoch.get("clock_type") != "monotonic_since_boot_ns":
            errors.append(f"{prefix}.clock_type debe ser monotonic_since_boot_ns")
        if epoch_id in epoch_points:
            errors.append(f"clock_epoch_id duplicado: {epoch_id}")
            continue

        sync_points = epoch.get("sync_points")
        if not isinstance(sync_points, list) or not sync_points:
            errors.append(f"{prefix}.sync_points debe contener al menos un punto")
            sync_points = []
        if status == "completed" and len(sync_points) < 2:
            errors.append(f"{prefix}.sync_points necesita dos puntos al cerrar la jornada")

        parsed_points: list[tuple[int, datetime]] = []
        for point_index, point in enumerate(sync_points):
            point_prefix = f"{prefix}.sync_points[{point_index}]"
            if not isinstance(point, dict):
                errors.append(f"{point_prefix} debe ser un objeto")
                continue
            elapsed_ns = _integer(
                point.get("elapsed_realtime_ns"),
                f"{point_prefix}.elapsed_realtime_ns",
                errors,
            )
            utc_time = _utc(point.get("utc_time"), f"{point_prefix}.utc_time", errors)
            _required_text(point.get("source"), f"{point_prefix}.source", errors)
            if elapsed_ns is not None and utc_time is not None:
                if parsed_points and elapsed_ns <= parsed_points[-1][0]:
                    errors.append(f"{point_prefix} no está en orden monotónico estricto")
                if parsed_points and utc_time <= parsed_points[-1][1]:
                    errors.append(f"{point_prefix} no está en orden UTC estricto")
                parsed_points.append((elapsed_ns, utc_time))
        if epoch_id is not None:
            epoch_points[epoch_id] = parsed_points

    trip_ids_value = session.get("trip_ids")
    trip_ids: list[str] = []
    if not isinstance(trip_ids_value, list):
        errors.append("session_metadata.trip_ids debe ser una lista")
    else:
        for index, value in enumerate(trip_ids_value):
            trip_id = _required_text(
                value, f"session_metadata.trip_ids[{index}]", errors, TRIP_ID_PATTERN
            )
            if trip_id is not None:
                if trip_id in trip_ids:
                    errors.append(f"trip_id duplicado en la jornada: {trip_id}")
                trip_ids.append(trip_id)
    return session_id, epoch_points, trip_ids


def _validate_gnss(
    records: Sequence[Mapping[str, Any]],
    path: Path,
    session_id: str,
    trip_id: str,
    epoch_id: str,
    clock_points: Sequence[tuple[int, datetime]],
    errors: list[str],
) -> list[int]:
    elapsed_values: list[int] = []
    sample_ids: set[str] = set()
    previous_utc: datetime | None = None
    for index, record in enumerate(records, start=1):
        prefix = f"{path}:{index}"
        _require_fields(record, GNSS_REQUIRED_FIELDS, prefix, errors)
        if record.get("schema_version") != SCHEMA_VERSION:
            errors.append(f"{prefix}.schema_version debe ser {SCHEMA_VERSION}")
        if record.get("session_id") != session_id:
            errors.append(f"{prefix}.session_id no coincide con la jornada")
        if record.get("trip_id") != trip_id:
            errors.append(f"{prefix}.trip_id no coincide con el recorrido")
        if record.get("clock_epoch_id") != epoch_id:
            errors.append(f"{prefix}.clock_epoch_id no coincide con el recorrido")

        sample_id = _required_text(record.get("sample_id"), f"{prefix}.sample_id", errors)
        expected_sample_id = f"gps-{index:06d}"
        if sample_id is not None:
            if sample_id in sample_ids:
                errors.append(f"{prefix}.sample_id está duplicado")
            sample_ids.add(sample_id)
            if sample_id != expected_sample_id:
                errors.append(f"{prefix}.sample_id debe ser {expected_sample_id}")

        elapsed_ns = _integer(
            record.get("elapsed_realtime_ns"), f"{prefix}.elapsed_realtime_ns", errors
        )
        utc_time = _utc(record.get("utc_time"), f"{prefix}.utc_time", errors)
        if elapsed_ns is not None:
            if elapsed_values and elapsed_ns <= elapsed_values[-1]:
                errors.append(f"{prefix} no está en orden monotónico estricto")
            elapsed_values.append(elapsed_ns)
        if utc_time is not None:
            if previous_utc is not None and utc_time < previous_utc:
                errors.append(f"{prefix} retrocede en UTC")
            previous_utc = utc_time
        _check_clock_alignment(utc_time, elapsed_ns, clock_points, prefix, errors)

        latitude = _number(record.get("latitude"), f"{prefix}.latitude", errors)
        longitude = _number(record.get("longitude"), f"{prefix}.longitude", errors)
        accuracy = _number(
            record.get("horizontal_accuracy_m"), f"{prefix}.horizontal_accuracy_m", errors
        )
        if latitude is not None and not -90 <= latitude <= 90:
            errors.append(f"{prefix}.latitude debe estar entre -90 y 90")
        if longitude is not None and not -180 <= longitude <= 180:
            errors.append(f"{prefix}.longitude debe estar entre -180 y 180")
        if accuracy is not None and accuracy < 0:
            errors.append(f"{prefix}.horizontal_accuracy_m no puede ser negativa")

        speed = record.get("speed_mps")
        if speed is not None:
            speed_number = _number(speed, f"{prefix}.speed_mps", errors)
            if speed_number is not None and speed_number < 0:
                errors.append(f"{prefix}.speed_mps no puede ser negativa")
        heading = record.get("heading_deg")
        if heading is not None:
            heading_number = _number(heading, f"{prefix}.heading_deg", errors)
            if heading_number is not None and not 0 <= heading_number < 360:
                errors.append(f"{prefix}.heading_deg debe estar entre 0 y menos de 360")
        _required_text(record.get("provider"), f"{prefix}.provider", errors)
    return elapsed_values


def _validate_events(
    records: Sequence[Mapping[str, Any]],
    path: Path,
    session_id: str,
    trip_id: str,
    epoch_id: str,
    trip_status: Any,
    clock_points: Sequence[tuple[int, datetime]],
    expected_segment_ids: Sequence[str],
    trip_started_ns: int | None,
    trip_ended_ns: int | None,
    errors: list[str],
) -> None:
    elapsed_values: list[int] = []
    event_ids: set[str] = set()
    event_types: list[str] = []
    open_pause = False
    started_segments: list[str] = []
    ended_segments: list[str] = []

    for index, record in enumerate(records, start=1):
        prefix = f"{path}:{index}"
        _require_fields(record, EVENT_REQUIRED_FIELDS, prefix, errors)
        if record.get("schema_version") != SCHEMA_VERSION:
            errors.append(f"{prefix}.schema_version debe ser {SCHEMA_VERSION}")
        if record.get("session_id") != session_id:
            errors.append(f"{prefix}.session_id no coincide con la jornada")
        if record.get("trip_id") != trip_id:
            errors.append(f"{prefix}.trip_id no coincide con el recorrido")
        if record.get("clock_epoch_id") != epoch_id:
            errors.append(f"{prefix}.clock_epoch_id no coincide con el recorrido")

        event_id = _required_text(record.get("event_id"), f"{prefix}.event_id", errors)
        expected_event_id = f"event-{index:06d}"
        if event_id is not None:
            if event_id in event_ids:
                errors.append(f"{prefix}.event_id está duplicado")
            event_ids.add(event_id)
            if event_id != expected_event_id:
                errors.append(f"{prefix}.event_id debe ser {expected_event_id}")

        event_type = record.get("event_type")
        if event_type not in EVENT_TYPES:
            errors.append(f"{prefix}.event_type no está permitido")
        else:
            event_types.append(event_type)
            if event_type == "pause_started":
                if open_pause:
                    errors.append(f"{prefix} abre una pausa cuando ya existe otra")
                open_pause = True
            elif event_type == "pause_ended":
                if not open_pause:
                    errors.append(f"{prefix} cierra una pausa inexistente")
                open_pause = False
            elif event_type in {"video_segment_started", "video_segment_ended"}:
                details = record.get("details")
                segment_id = details.get("segment_id") if isinstance(details, dict) else None
                if not isinstance(segment_id, str) or not segment_id:
                    errors.append(f"{prefix}.details.segment_id es requerido")
                elif event_type == "video_segment_started":
                    started_segments.append(segment_id)
                else:
                    ended_segments.append(segment_id)

        elapsed_ns = _integer(
            record.get("elapsed_realtime_ns"), f"{prefix}.elapsed_realtime_ns", errors
        )
        utc_time = _utc(record.get("utc_time"), f"{prefix}.utc_time", errors)
        if elapsed_ns is not None:
            if elapsed_values and elapsed_ns <= elapsed_values[-1]:
                errors.append(f"{prefix} no está en orden monotónico estricto")
            if trip_started_ns is not None and elapsed_ns < trip_started_ns:
                errors.append(f"{prefix} ocurre antes de comenzar el recorrido")
            if trip_ended_ns is not None and elapsed_ns > trip_ended_ns:
                errors.append(f"{prefix} ocurre después de terminar el recorrido")
            elapsed_values.append(elapsed_ns)
        _check_clock_alignment(utc_time, elapsed_ns, clock_points, prefix, errors)

    if records and event_types and event_types[0] != "trip_started":
        errors.append(f"{path} debe comenzar con trip_started")
    if started_segments != list(expected_segment_ids[: len(started_segments)]):
        errors.append(f"{path} inicia segmentos que no coinciden con trip_metadata.json")
    if ended_segments != started_segments[: len(ended_segments)]:
        errors.append(f"{path} cierra segmentos que no coinciden con los iniciados")
    if trip_status == "completed":
        if not event_types or event_types[-1] != "trip_completed":
            errors.append(f"{path} debe terminar con trip_completed")
        if open_pause:
            errors.append(f"{path} deja una pausa abierta en un recorrido completed")
        if started_segments != ended_segments:
            errors.append(f"{path} no cierra exactamente los segmentos iniciados")
        if started_segments != list(expected_segment_ids):
            errors.append(f"{path} no registra todos los segmentos declarados")
        if elapsed_values and trip_started_ns is not None and elapsed_values[0] != trip_started_ns:
            errors.append(f"{path} no sitúa trip_started en el inicio del recorrido")
        if elapsed_values and trip_ended_ns is not None and elapsed_values[-1] != trip_ended_ns:
            errors.append(f"{path} no sitúa trip_completed en el final del recorrido")


def _validate_trip(
    trip_root: Path,
    session_id: str,
    expected_trip_id: str,
    session_status: Any,
    epoch_points: Mapping[str, Sequence[tuple[int, datetime]]],
    require_media_files: bool,
    errors: list[str],
) -> tuple[int, int, int]:
    metadata_path = trip_root / "trip_metadata.json"
    trip = _load_json(metadata_path, errors)
    if trip.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{metadata_path}.schema_version debe ser {SCHEMA_VERSION}")
    if trip.get("session_id") != session_id:
        errors.append(f"{metadata_path}.session_id no coincide con la jornada")
    if trip.get("trip_id") != expected_trip_id:
        errors.append(f"{metadata_path}.trip_id no coincide con su carpeta")
    if trip_root.name != expected_trip_id:
        errors.append(f"la carpeta {trip_root} no coincide con el trip_id esperado")

    _required_text(trip.get("route_id"), f"{metadata_path}.route_id", errors)
    _integer(trip.get("pass_number"), f"{metadata_path}.pass_number", errors, minimum=1)
    _required_text(trip.get("mount_version"), f"{metadata_path}.mount_version", errors)

    trip_status = trip.get("status")
    if trip_status not in {"active", "completed", "interrupted"}:
        errors.append(f"{metadata_path}.status debe ser active, completed o interrupted")
    if session_status == "completed" and trip_status != "completed":
        errors.append(f"la jornada completed contiene el recorrido {expected_trip_id} sin cerrar")

    epoch_id = _required_text(
        trip.get("clock_epoch_id"), f"{metadata_path}.clock_epoch_id", errors
    )
    clock_points = epoch_points.get(epoch_id or "", ())
    if epoch_id is not None and epoch_id not in epoch_points:
        errors.append(f"{metadata_path}.clock_epoch_id no existe en la jornada")

    started_ns = _integer(
        trip.get("started_elapsed_realtime_ns"),
        f"{metadata_path}.started_elapsed_realtime_ns",
        errors,
    )
    ended_value = trip.get("ended_elapsed_realtime_ns")
    ended_ns = (
        None
        if ended_value is None
        else _integer(ended_value, f"{metadata_path}.ended_elapsed_realtime_ns", errors)
    )
    started_utc = _utc(trip.get("started_at_utc"), f"{metadata_path}.started_at_utc", errors)
    ended_utc_value = trip.get("ended_at_utc")
    ended_utc = (
        None
        if ended_utc_value is None
        else _utc(ended_utc_value, f"{metadata_path}.ended_at_utc", errors)
    )
    _check_clock_alignment(
        started_utc, started_ns, clock_points, f"{metadata_path}.started_at_utc", errors
    )
    _check_clock_alignment(
        ended_utc, ended_ns, clock_points, f"{metadata_path}.ended_at_utc", errors
    )
    if trip_status == "completed" and (ended_ns is None or ended_utc is None):
        errors.append(f"{metadata_path} debe tener tiempos finales cuando está completed")
    if started_ns is not None and ended_ns is not None and ended_ns < started_ns:
        errors.append(f"{metadata_path} termina antes de comenzar")

    video = trip.get("video")
    if not isinstance(video, dict):
        errors.append(f"{metadata_path}.video debe ser un objeto")
        video = {}
    if video.get("container") != "mp4":
        errors.append(f"{metadata_path}.video.container debe ser mp4")
    if video.get("codec") != "h264":
        errors.append(f"{metadata_path}.video.codec debe ser h264")
    _integer(video.get("width"), f"{metadata_path}.video.width", errors, minimum=1)
    _integer(video.get("height"), f"{metadata_path}.video.height", errors, minimum=1)
    nominal_fps = _number(video.get("nominal_fps"), f"{metadata_path}.video.nominal_fps", errors)
    if nominal_fps is not None and nominal_fps <= 0:
        errors.append(f"{metadata_path}.video.nominal_fps debe ser mayor que cero")

    segments_value = video.get("segments")
    if not isinstance(segments_value, list):
        errors.append(f"{metadata_path}.video.segments debe ser una lista")
        segments_value = []
    if trip_status == "completed" and not segments_value:
        errors.append(f"{metadata_path} no contiene segmentos de video")

    segment_intervals: list[tuple[int, int | None]] = []
    segment_ids: list[str] = []
    previous_last_ns: int | None = None
    for index, segment in enumerate(segments_value, start=1):
        prefix = f"{metadata_path}.video.segments[{index - 1}]"
        if not isinstance(segment, dict):
            errors.append(f"{prefix} debe ser un objeto")
            continue
        expected_segment_id = f"seg-{index:04d}"
        segment_ids.append(expected_segment_id)
        if segment.get("segment_id") != expected_segment_id:
            errors.append(f"{prefix}.segment_id debe ser {expected_segment_id}")
        expected_name = f"{expected_trip_id}_video_{index:04d}.mp4"
        relative = _relative_path(segment.get("relative_path"), f"{prefix}.relative_path", errors)
        if relative is not None:
            expected_relative = PurePosixPath("video") / expected_name
            if relative != expected_relative:
                errors.append(f"{prefix}.relative_path debe ser {expected_relative.as_posix()}")
            media_path = trip_root.joinpath(*relative.parts)
            if require_media_files and not media_path.is_file():
                errors.append(f"falta el segmento de video {media_path}")

        segment_status = segment.get("status")
        if segment_status not in {"complete", "partial"}:
            errors.append(f"{prefix}.status debe ser complete o partial")
        if trip_status == "completed" and segment_status != "complete":
            errors.append(f"{prefix} no puede ser partial en un recorrido completed")

        first_ns = _integer(
            segment.get("first_frame_elapsed_realtime_ns"),
            f"{prefix}.first_frame_elapsed_realtime_ns",
            errors,
        )
        last_ns_value = segment.get("last_frame_elapsed_realtime_ns")
        last_ns = (
            None
            if last_ns_value is None
            else _integer(last_ns_value, f"{prefix}.last_frame_elapsed_realtime_ns", errors)
        )
        first_media = _integer(
            segment.get("first_frame_media_time_us"),
            f"{prefix}.first_frame_media_time_us",
            errors,
        )
        last_media_value = segment.get("last_frame_media_time_us")
        last_media = (
            None
            if last_media_value is None
            else _integer(last_media_value, f"{prefix}.last_frame_media_time_us", errors)
        )
        if segment_status == "complete" and (last_ns is None or last_media is None):
            errors.append(f"{prefix} necesita tiempos finales cuando está complete")
        if first_ns is not None:
            if started_ns is not None and first_ns < started_ns:
                errors.append(f"{prefix} comienza antes del recorrido")
            if ended_ns is not None and first_ns > ended_ns:
                errors.append(f"{prefix} comienza después del recorrido")
            if previous_last_ns is not None and first_ns < previous_last_ns:
                errors.append(f"{prefix} se solapa con el segmento anterior")
            segment_intervals.append((first_ns, last_ns))
        if first_ns is not None and last_ns is not None and last_ns < first_ns:
            errors.append(f"{prefix} termina antes de comenzar")
        if ended_ns is not None and last_ns is not None and last_ns > ended_ns:
            errors.append(f"{prefix} termina después del recorrido")
        if first_media is not None and last_media is not None and last_media < first_media:
            errors.append(f"{prefix} tiene PTS final anterior al inicial")
        if last_ns is not None:
            previous_last_ns = last_ns

    gnss_meta = trip.get("gnss")
    if not isinstance(gnss_meta, dict):
        errors.append(f"{metadata_path}.gnss debe ser un objeto")
        gnss_meta = {}
    if gnss_meta.get("format") != "application/x-ndjson":
        errors.append(f"{metadata_path}.gnss.format debe ser application/x-ndjson")
    gnss_relative = _relative_path(
        gnss_meta.get("relative_path"), f"{metadata_path}.gnss.relative_path", errors
    )
    if gnss_relative != PurePosixPath("gnss.jsonl"):
        errors.append(f"{metadata_path}.gnss.relative_path debe ser gnss.jsonl")
    gnss_path = trip_root / "gnss.jsonl"
    gnss_records = _load_jsonl(gnss_path, errors)
    gnss_elapsed = _validate_gnss(
        gnss_records,
        gnss_path,
        session_id,
        expected_trip_id,
        epoch_id or "",
        clock_points,
        errors,
    )
    declared_sample_count = gnss_meta.get("sample_count")
    if declared_sample_count is not None:
        parsed_count = _integer(
            declared_sample_count, f"{metadata_path}.gnss.sample_count", errors
        )
        if parsed_count is not None and parsed_count != len(gnss_records):
            errors.append(f"{metadata_path}.gnss.sample_count no coincide con gnss.jsonl")

    closed_video_intervals = [interval for interval in segment_intervals if interval[1] is not None]
    if trip_status == "completed" and closed_video_intervals:
        first_frame_ns = closed_video_intervals[0][0]
        last_frame_ns = closed_video_intervals[-1][1]
        if not gnss_elapsed:
            errors.append(f"{gnss_path} no contiene muestras para cubrir el video")
        else:
            if gnss_elapsed[0] > first_frame_ns:
                errors.append(f"{gnss_path} comienza después del primer cuadro")
            if last_frame_ns is not None and gnss_elapsed[-1] < last_frame_ns:
                errors.append(f"{gnss_path} termina antes del último cuadro")

    events_meta = trip.get("events")
    if not isinstance(events_meta, dict):
        errors.append(f"{metadata_path}.events debe ser un objeto")
        events_meta = {}
    if events_meta.get("format") != "application/x-ndjson":
        errors.append(f"{metadata_path}.events.format debe ser application/x-ndjson")
    events_relative = _relative_path(
        events_meta.get("relative_path"), f"{metadata_path}.events.relative_path", errors
    )
    if events_relative != PurePosixPath("events.jsonl"):
        errors.append(f"{metadata_path}.events.relative_path debe ser events.jsonl")
    events_path = trip_root / "events.jsonl"
    event_records = _load_jsonl(events_path, errors)
    _validate_events(
        event_records,
        events_path,
        session_id,
        expected_trip_id,
        epoch_id or "",
        trip_status,
        clock_points,
        segment_ids,
        started_ns,
        ended_ns,
        errors,
    )
    declared_event_count = events_meta.get("event_count")
    if declared_event_count is not None:
        parsed_count = _integer(
            declared_event_count, f"{metadata_path}.events.event_count", errors
        )
        if parsed_count is not None and parsed_count != len(event_records):
            errors.append(f"{metadata_path}.events.event_count no coincide con events.jsonl")

    return len(segments_value), len(gnss_records), len(event_records)


def validate_capture_directory(
    root: str | Path, *, require_media_files: bool = True
) -> CaptureValidationReport:
    """Valida contratos y relaciones de todos los archivos de una jornada."""

    capture_root = Path(root)
    errors: list[str] = []
    session_path = capture_root / "session_metadata.json"
    session = _load_json(session_path, errors)
    session_id, epoch_points, trip_ids = _validate_session(capture_root, session, errors)
    effective_session_id = session_id or ""
    session_status = session.get("status")

    trips_root = capture_root / "trips"
    if not trips_root.is_dir():
        errors.append(f"falta la carpeta {trips_root}")

    segment_count = 0
    sample_count = 0
    event_count = 0
    for trip_id in trip_ids:
        counts = _validate_trip(
            trips_root / trip_id,
            effective_session_id,
            trip_id,
            session_status,
            epoch_points,
            require_media_files,
            errors,
        )
        segment_count += counts[0]
        sample_count += counts[1]
        event_count += counts[2]

    if trips_root.is_dir():
        actual_trip_dirs = sorted(path.name for path in trips_root.iterdir() if path.is_dir())
        if actual_trip_dirs != sorted(trip_ids):
            errors.append(
                "las carpetas en trips/ no coinciden con session_metadata.trip_ids"
            )

    if errors:
        raise CaptureValidationError(errors)
    return CaptureValidationReport(
        session_id=effective_session_id,
        trip_count=len(trip_ids),
        video_segment_count=segment_count,
        gnss_sample_count=sample_count,
        event_count=event_count,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Valida una jornada con video, reloj común, GNSS y eventos."
    )
    parser.add_argument("root", type=Path, help="Carpeta raíz de la jornada")
    parser.add_argument(
        "--allow-missing-media",
        action="store_true",
        help="Valida el contrato sin exigir los MP4; útil para el ejemplo versionado.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = validate_capture_directory(
            args.root, require_media_files=not args.allow_missing_media
        )
    except CaptureValidationError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(
        f"Jornada {report.session_id} válida: {report.trip_count} recorrido(s), "
        f"{report.video_segment_count} segmento(s), "
        f"{report.gnss_sample_count} muestra(s) GNSS y "
        f"{report.event_count} evento(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
