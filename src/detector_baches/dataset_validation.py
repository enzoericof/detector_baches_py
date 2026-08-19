"""Validación cruzada de un manifiesto y su índice de muestras."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import isfinite
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "0.1.0"
DATASET_ID_PATTERN = re.compile(r"^dataset-[a-z0-9-]+-v[0-9]+\.[0-9]+$")
SEMVER_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
SESSION_ID_PATTERN = re.compile(
    r"^session-[0-9]{8}-[0-9]{4}-[A-Za-z0-9][A-Za-z0-9_-]*$"
)
TRIP_ID_PATTERN = re.compile(r"^trip-[0-9]{8}-[0-9]{4}-R[0-9]{2}-P[0-9]{2}$")
SEGMENT_ID_PATTERN = re.compile(r"^seg-[0-9]{4}$")
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SPLIT_NAMES = ("train", "validation", "test")
NEGATIVE_CATEGORIES = {"shadow", "patch", "manhole_cover", "crack", "puddle", "other"}
SAMPLE_REQUIRED_FIELDS = {
    "schema_version",
    "dataset_id",
    "sample_id",
    "split",
    "source",
    "image",
    "annotation",
    "is_negative",
    "negative_categories",
    "selection_reason",
}


class DatasetValidationError(ValueError):
    """Agrupa todos los problemas encontrados en una versión del dataset."""

    def __init__(self, errors: Sequence[str]) -> None:
        self.errors = tuple(errors)
        detail = "\n".join(f"- {error}" for error in self.errors)
        super().__init__(f"dataset inválido:\n{detail}")


@dataclass(frozen=True, slots=True)
class DatasetValidationReport:
    """Resumen de una versión validada."""

    dataset_id: str
    sample_count: int
    positive_sample_count: int
    negative_sample_count: int
    annotation_count: int


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
    value: Any,
    field: str,
    errors: list[str],
    pattern: re.Pattern[str] | None = None,
) -> str | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} debe ser texto no vacío")
        return None
    if pattern is not None and pattern.fullmatch(value) is None:
        errors.append(f"{field} tiene un formato inválido: {value!r}")
        return None
    return value


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
    return parsed


def _relative_path(value: Any, field: str, errors: list[str]) -> PurePosixPath | None:
    text = _required_text(value, field, errors)
    if text is None:
        return None
    path = PurePosixPath(text)
    if "\\" in text or path.is_absolute() or ".." in path.parts or path.as_posix() != text:
        errors.append(f"{field} debe ser una ruta relativa segura con separadores /")
        return None
    return path


def _hash_text(value: Any, field: str, errors: list[str]) -> str | None:
    return _required_text(value, field, errors, HASH_PATTERN)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_artifact(
    root: Path,
    relative: PurePosixPath | None,
    expected_hash: str | None,
    field: str,
    require_artifacts: bool,
    errors: list[str],
) -> None:
    if relative is None:
        return
    path = root.joinpath(*relative.parts)
    if not path.is_file():
        if require_artifacts:
            errors.append(f"falta el artefacto {path}")
        return
    if expected_hash is not None and _sha256(path) != expected_hash:
        errors.append(f"{field} no coincide con el contenido de {path}")


def _validate_manifest_identity(
    root: Path, manifest: Mapping[str, Any], errors: list[str]
) -> tuple[str, str]:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"manifest.schema_version debe ser {SCHEMA_VERSION}")
    dataset_id = _required_text(
        manifest.get("dataset_id"), "manifest.dataset_id", errors, DATASET_ID_PATTERN
    )
    if dataset_id is not None and root.name != dataset_id:
        errors.append(f"la carpeta del dataset debe llamarse {dataset_id!r}, no {root.name!r}")
    _required_text(
        manifest.get("dataset_version"),
        "manifest.dataset_version",
        errors,
        SEMVER_PATTERN,
    )
    parent_id = manifest.get("parent_dataset_id")
    if parent_id is not None:
        _required_text(parent_id, "manifest.parent_dataset_id", errors, DATASET_ID_PATTERN)
        if parent_id == dataset_id:
            errors.append("manifest.parent_dataset_id no puede ser el dataset actual")

    status = manifest.get("status")
    if status not in {"draft", "frozen"}:
        errors.append("manifest.status debe ser draft o frozen")
    _required_text(manifest.get("title"), "manifest.title", errors)
    _required_text(manifest.get("description"), "manifest.description", errors)
    created_at = _utc(manifest.get("created_at_utc"), "manifest.created_at_utc", errors)
    frozen_value = manifest.get("frozen_at_utc")
    frozen_at = (
        None
        if frozen_value is None
        else _utc(frozen_value, "manifest.frozen_at_utc", errors)
    )
    revision = manifest.get("code_revision")
    if revision is not None:
        _required_text(
            revision,
            "manifest.code_revision",
            errors,
            re.compile(r"^[0-9a-f]{7,40}$"),
        )
    if status == "frozen":
        if frozen_at is None:
            errors.append("un dataset frozen debe tener frozen_at_utc")
        if revision is None:
            errors.append("un dataset frozen debe tener code_revision")
    if created_at is not None and frozen_at is not None and frozen_at < created_at:
        errors.append("manifest.frozen_at_utc no puede preceder created_at_utc")
    return dataset_id or "", status if isinstance(status, str) else ""


def _validate_task(manifest: Mapping[str, Any], errors: list[str]) -> list[str]:
    task = manifest.get("task")
    if not isinstance(task, dict):
        errors.append("manifest.task debe ser un objeto")
        return []
    if task.get("type") != "object_detection":
        errors.append("manifest.task.type debe ser object_detection")
    if task.get("annotation_format") != "yolo_bbox_normalized":
        errors.append("manifest.task.annotation_format debe ser yolo_bbox_normalized")
    classes = task.get("classes")
    if not isinstance(classes, list) or not classes:
        errors.append("manifest.task.classes debe contener al menos una clase")
        return []

    class_names: list[str] = []
    for index, item in enumerate(classes):
        prefix = f"manifest.task.classes[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} debe ser un objeto")
            continue
        if item.get("id") != index:
            errors.append(f"{prefix}.id debe ser {index}")
        name = _required_text(item.get("name"), f"{prefix}.name", errors)
        if name is not None:
            if name in class_names:
                errors.append(f"nombre de clase duplicado: {name}")
            class_names.append(name)
    return class_names


def _validate_selection(manifest: Mapping[str, Any], errors: list[str]) -> set[str]:
    selection = manifest.get("selection")
    if not isinstance(selection, dict):
        errors.append("manifest.selection debe ser un objeto")
        return set()
    if selection.get("unit") != "frame":
        errors.append("manifest.selection.unit debe ser frame")
    _required_text(selection.get("strategy"), "manifest.selection.strategy", errors)
    _integer(
        selection.get("minimum_spacing_ms"),
        "manifest.selection.minimum_spacing_ms",
        errors,
    )
    criteria = selection.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        errors.append("manifest.selection.criteria debe contener al menos un criterio")
    else:
        for index, criterion in enumerate(criteria):
            _required_text(criterion, f"manifest.selection.criteria[{index}]", errors)

    categories = selection.get("negative_categories")
    declared: set[str] = set()
    if not isinstance(categories, list):
        errors.append("manifest.selection.negative_categories debe ser una lista")
    else:
        for category in categories:
            if category not in NEGATIVE_CATEGORIES:
                errors.append(f"categoría negativa no permitida: {category!r}")
            elif category in declared:
                errors.append(f"categoría negativa duplicada: {category}")
            else:
                declared.add(category)
    return declared


def _validate_sources(
    manifest: Mapping[str, Any], errors: list[str]
) -> dict[str, set[tuple[str, str]]]:
    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("manifest.sources debe contener al menos una fuente")
        return {}

    source_trips: dict[str, set[tuple[str, str]]] = {}
    trip_owners: dict[str, str] = {}
    for source_index, source in enumerate(sources):
        prefix = f"manifest.sources[{source_index}]"
        if not isinstance(source, dict):
            errors.append(f"{prefix} debe ser un objeto")
            continue
        source_id = _required_text(source.get("source_id"), f"{prefix}.source_id", errors)
        if source_id in source_trips:
            errors.append(f"source_id duplicado: {source_id}")
            continue
        if source.get("kind") not in {"local_capture", "external_dataset", "synthetic"}:
            errors.append(f"{prefix}.kind no está permitido")
        _required_text(source.get("name"), f"{prefix}.name", errors)
        _required_text(source.get("license"), f"{prefix}.license", errors)
        trips = source.get("trips")
        if not isinstance(trips, list):
            errors.append(f"{prefix}.trips debe ser una lista")
            trips = []
        declared: set[tuple[str, str]] = set()
        for trip_index, trip in enumerate(trips):
            trip_prefix = f"{prefix}.trips[{trip_index}]"
            if not isinstance(trip, dict):
                errors.append(f"{trip_prefix} debe ser un objeto")
                continue
            session_id = _required_text(
                trip.get("session_id"),
                f"{trip_prefix}.session_id",
                errors,
                SESSION_ID_PATTERN,
            )
            trip_id = _required_text(
                trip.get("trip_id"),
                f"{trip_prefix}.trip_id",
                errors,
                TRIP_ID_PATTERN,
            )
            if trip.get("capture_quality_class") not in {"A", "B", "C", "not_applicable"}:
                errors.append(f"{trip_prefix}.capture_quality_class no está permitida")
            if session_id is not None and trip_id is not None:
                pair = (session_id, trip_id)
                if pair in declared:
                    errors.append(f"{trip_prefix} está duplicado")
                declared.add(pair)
                previous_owner = trip_owners.get(trip_id)
                if previous_owner is not None and previous_owner != source_id:
                    errors.append(f"{trip_id} pertenece a más de una fuente")
                elif source_id is not None:
                    trip_owners[trip_id] = source_id
        if source_id is not None:
            source_trips[source_id] = declared
    return source_trips


def _validate_splits(
    manifest: Mapping[str, Any],
    source_trips: Mapping[str, set[tuple[str, str]]],
    errors: list[str],
) -> tuple[dict[str, str], dict[str, int]]:
    policy = manifest.get("split_policy")
    if not isinstance(policy, dict):
        errors.append("manifest.split_policy debe ser un objeto")
    else:
        if policy.get("strategy") != "grouped_holdout":
            errors.append("manifest.split_policy.strategy debe ser grouped_holdout")
        if policy.get("grouping_key") != "trip_id":
            errors.append("manifest.split_policy.grouping_key debe ser trip_id")
        _integer(policy.get("seed"), "manifest.split_policy.seed", errors)
        ratios = policy.get("target_ratios")
        if not isinstance(ratios, dict):
            errors.append("manifest.split_policy.target_ratios debe ser un objeto")
        else:
            total = 0.0
            for split in SPLIT_NAMES:
                ratio = _number(
                    ratios.get(split), f"manifest.split_policy.target_ratios.{split}", errors
                )
                if ratio is not None:
                    if not 0 <= ratio <= 1:
                        errors.append(f"proporción de {split} debe estar entre 0 y 1")
                    total += ratio
            if abs(total - 1.0) > 1e-9:
                errors.append("las proporciones objetivo deben sumar 1")

    declared_source_trip_ids = {
        trip_id for trips in source_trips.values() for _, trip_id in trips
    }
    splits = manifest.get("splits")
    if not isinstance(splits, list):
        errors.append("manifest.splits debe ser una lista")
        return {}, {}

    trip_to_split: dict[str, str] = {}
    declared_counts: dict[str, int] = {}
    seen_names: set[str] = set()
    for index, split_item in enumerate(splits):
        prefix = f"manifest.splits[{index}]"
        if not isinstance(split_item, dict):
            errors.append(f"{prefix} debe ser un objeto")
            continue
        name = split_item.get("name")
        if name not in SPLIT_NAMES:
            errors.append(f"{prefix}.name no está permitido")
            continue
        if name in seen_names:
            errors.append(f"partición duplicada: {name}")
        seen_names.add(name)
        count = _integer(split_item.get("sample_count"), f"{prefix}.sample_count", errors)
        if count is not None:
            declared_counts[name] = count
        trip_ids = split_item.get("trip_ids")
        if not isinstance(trip_ids, list):
            errors.append(f"{prefix}.trip_ids debe ser una lista")
            continue
        for trip_index, value in enumerate(trip_ids):
            trip_id = _required_text(
                value, f"{prefix}.trip_ids[{trip_index}]", errors, TRIP_ID_PATTERN
            )
            if trip_id is None:
                continue
            if trip_id not in declared_source_trip_ids:
                errors.append(f"{trip_id} no está declarado en manifest.sources")
            previous_split = trip_to_split.get(trip_id)
            if previous_split is not None:
                errors.append(
                    f"fuga de partición: {trip_id} aparece en {previous_split} y {name}"
                )
            else:
                trip_to_split[trip_id] = name
    if seen_names != set(SPLIT_NAMES):
        errors.append("manifest.splits debe declarar train, validation y test exactamente una vez")
    return trip_to_split, declared_counts


def _validate_sample(
    record: Mapping[str, Any],
    line_number: int,
    index_path: Path,
    root: Path,
    dataset_id: str,
    class_names: Sequence[str],
    negative_categories: set[str],
    source_trips: Mapping[str, set[tuple[str, str]]],
    trip_to_split: Mapping[str, str],
    require_artifacts: bool,
    seen_sample_ids: set[str],
    seen_paths: set[PurePosixPath],
    errors: list[str],
) -> tuple[str | None, bool | None, int, Counter[str]]:
    prefix = f"{index_path}:{line_number}"
    missing = sorted(SAMPLE_REQUIRED_FIELDS.difference(record))
    if missing:
        errors.append(f"{prefix} omite campos requeridos: {', '.join(missing)}")
    if record.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{prefix}.schema_version debe ser {SCHEMA_VERSION}")
    if record.get("dataset_id") != dataset_id:
        errors.append(f"{prefix}.dataset_id no coincide con manifest.json")

    sample_id = _required_text(
        record.get("sample_id"),
        f"{prefix}.sample_id",
        errors,
        re.compile(r"^sample-[0-9]{6}$"),
    )
    expected_sample_id = f"sample-{line_number:06d}"
    if sample_id is not None:
        if sample_id in seen_sample_ids:
            errors.append(f"{prefix}.sample_id está duplicado")
        seen_sample_ids.add(sample_id)
        if sample_id != expected_sample_id:
            errors.append(f"{prefix}.sample_id debe ser {expected_sample_id}")

    split = record.get("split")
    if split not in SPLIT_NAMES:
        errors.append(f"{prefix}.split no está permitido")
        split = None

    source = record.get("source")
    trip_id: str | None = None
    if not isinstance(source, dict):
        errors.append(f"{prefix}.source debe ser un objeto")
    else:
        source_id = _required_text(source.get("source_id"), f"{prefix}.source.source_id", errors)
        session_id = _required_text(
            source.get("session_id"),
            f"{prefix}.source.session_id",
            errors,
            SESSION_ID_PATTERN,
        )
        trip_id = _required_text(
            source.get("trip_id"),
            f"{prefix}.source.trip_id",
            errors,
            TRIP_ID_PATTERN,
        )
        _required_text(
            source.get("segment_id"),
            f"{prefix}.source.segment_id",
            errors,
            SEGMENT_ID_PATTERN,
        )
        _integer(
            source.get("frame_media_time_us"),
            f"{prefix}.source.frame_media_time_us",
            errors,
        )
        _integer(
            source.get("frame_elapsed_realtime_ns"),
            f"{prefix}.source.frame_elapsed_realtime_ns",
            errors,
        )
        if source_id is not None and session_id is not None and trip_id is not None:
            if (session_id, trip_id) not in source_trips.get(source_id, set()):
                errors.append(f"{prefix}.source no está declarado en manifest.sources")
        if trip_id is not None and split is not None:
            assigned_split = trip_to_split.get(trip_id)
            if assigned_split != split:
                errors.append(
                    f"{prefix} asigna {trip_id} a {split}, pero el manifiesto indica "
                    f"{assigned_split!r}"
                )

    image = record.get("image")
    if not isinstance(image, dict):
        errors.append(f"{prefix}.image debe ser un objeto")
        image = {}
    image_relative = _relative_path(
        image.get("relative_path"), f"{prefix}.image.relative_path", errors
    )
    if image_relative is not None and sample_id is not None and split is not None:
        expected = PurePosixPath("images") / split / f"{sample_id}.jpg"
        if image_relative != expected:
            errors.append(f"{prefix}.image.relative_path debe ser {expected.as_posix()}")
    _integer(image.get("width"), f"{prefix}.image.width", errors, minimum=1)
    _integer(image.get("height"), f"{prefix}.image.height", errors, minimum=1)
    image_hash = _hash_text(image.get("sha256"), f"{prefix}.image.sha256", errors)

    annotation = record.get("annotation")
    if not isinstance(annotation, dict):
        errors.append(f"{prefix}.annotation debe ser un objeto")
        annotation = {}
    annotation_relative = _relative_path(
        annotation.get("relative_path"), f"{prefix}.annotation.relative_path", errors
    )
    if annotation_relative is not None and sample_id is not None and split is not None:
        expected = PurePosixPath("labels") / split / f"{sample_id}.txt"
        if annotation_relative != expected:
            errors.append(f"{prefix}.annotation.relative_path debe ser {expected.as_posix()}")
    if annotation.get("format") != "yolo_bbox_normalized":
        errors.append(f"{prefix}.annotation.format debe ser yolo_bbox_normalized")
    object_count = _integer(
        annotation.get("object_count"), f"{prefix}.annotation.object_count", errors
    )
    annotation_hash = _hash_text(
        annotation.get("sha256"), f"{prefix}.annotation.sha256", errors
    )
    class_counts_value = annotation.get("class_counts")
    class_counter: Counter[str] = Counter()
    if not isinstance(class_counts_value, dict):
        errors.append(f"{prefix}.annotation.class_counts debe ser un objeto")
    else:
        for class_name, value in class_counts_value.items():
            if class_name not in class_names:
                errors.append(f"{prefix} usa una clase no declarada: {class_name}")
                continue
            count = _integer(value, f"{prefix}.annotation.class_counts.{class_name}", errors)
            if count is not None:
                class_counter[class_name] = count
        if object_count is not None and sum(class_counter.values()) != object_count:
            errors.append(f"{prefix}.annotation.class_counts no suma object_count")

    is_negative = record.get("is_negative")
    if not isinstance(is_negative, bool):
        errors.append(f"{prefix}.is_negative debe ser booleano")
        is_negative = None
    categories_value = record.get("negative_categories")
    categories: set[str] = set()
    if not isinstance(categories_value, list):
        errors.append(f"{prefix}.negative_categories debe ser una lista")
    else:
        for category in categories_value:
            if category not in NEGATIVE_CATEGORIES:
                errors.append(f"{prefix} usa categoría negativa no permitida: {category!r}")
            elif category not in negative_categories:
                errors.append(f"{prefix} usa categoría no declarada por selection: {category}")
            elif category in categories:
                errors.append(f"{prefix} repite la categoría negativa {category}")
            else:
                categories.add(category)
    if is_negative is True:
        if object_count != 0:
            errors.append(f"{prefix} es negativo pero tiene anotaciones")
        if not categories:
            errors.append(f"{prefix} es negativo pero no indica su categoría")
    elif is_negative is False:
        if object_count is not None and object_count <= 0:
            errors.append(f"{prefix} es positivo pero no tiene anotaciones")
        if categories:
            errors.append(f"{prefix} es positivo pero declara categorías negativas")
    _required_text(record.get("selection_reason"), f"{prefix}.selection_reason", errors)

    for relative, field in (
        (image_relative, "image.relative_path"),
        (annotation_relative, "annotation.relative_path"),
    ):
        if relative is not None:
            if relative in seen_paths:
                errors.append(f"{prefix}.{field} está duplicada: {relative.as_posix()}")
            seen_paths.add(relative)

    _check_artifact(
        root,
        image_relative,
        image_hash,
        f"{prefix}.image.sha256",
        require_artifacts,
        errors,
    )
    _check_artifact(
        root,
        annotation_relative,
        annotation_hash,
        f"{prefix}.annotation.sha256",
        require_artifacts,
        errors,
    )
    return split, is_negative, object_count or 0, class_counter


def _validate_statistics(
    manifest: Mapping[str, Any],
    sample_count: int,
    positive_count: int,
    negative_count: int,
    annotation_count: int,
    split_counts: Counter[str],
    class_counts: Counter[str],
    declared_split_counts: Mapping[str, int],
    class_names: Sequence[str],
    errors: list[str],
) -> None:
    for split in SPLIT_NAMES:
        if declared_split_counts.get(split) != split_counts[split]:
            errors.append(f"manifest.splits[{split}].sample_count no coincide con samples.jsonl")

    statistics = manifest.get("statistics")
    if not isinstance(statistics, dict):
        errors.append("manifest.statistics debe ser un objeto")
        return
    expected_scalars = {
        "sample_count": sample_count,
        "positive_sample_count": positive_count,
        "negative_sample_count": negative_count,
        "annotation_count": annotation_count,
    }
    for field, expected in expected_scalars.items():
        value = _integer(statistics.get(field), f"manifest.statistics.{field}", errors)
        if value is not None and value != expected:
            errors.append(f"manifest.statistics.{field} debe ser {expected}")

    by_split = statistics.get("by_split")
    if not isinstance(by_split, dict):
        errors.append("manifest.statistics.by_split debe ser un objeto")
    else:
        for split in SPLIT_NAMES:
            value = _integer(
                by_split.get(split), f"manifest.statistics.by_split.{split}", errors
            )
            if value is not None and value != split_counts[split]:
                errors.append(
                    f"manifest.statistics.by_split.{split} debe ser {split_counts[split]}"
                )

    by_class = statistics.get("by_class")
    if not isinstance(by_class, dict):
        errors.append("manifest.statistics.by_class debe ser un objeto")
    else:
        unknown_classes = sorted(set(by_class).difference(class_names))
        if unknown_classes:
            errors.append(
                "manifest.statistics.by_class contiene clases desconocidas: "
                + ", ".join(unknown_classes)
            )
        for class_name in class_names:
            value = _integer(
                by_class.get(class_name),
                f"manifest.statistics.by_class.{class_name}",
                errors,
            )
            if value is not None and value != class_counts[class_name]:
                errors.append(
                    f"manifest.statistics.by_class.{class_name} debe ser "
                    f"{class_counts[class_name]}"
                )


def _validate_governance(
    manifest: Mapping[str, Any], status: str, errors: list[str]
) -> None:
    governance = manifest.get("governance")
    if not isinstance(governance, dict):
        errors.append("manifest.governance debe ser un objeto")
        return
    _required_text(
        governance.get("dataset_license"), "manifest.governance.dataset_license", errors
    )
    annotation_status = governance.get("annotation_review_status")
    privacy_status = governance.get("privacy_review_status")
    allowed = {"pending", "in_progress", "complete"}
    if annotation_status not in allowed:
        errors.append("manifest.governance.annotation_review_status no está permitido")
    if privacy_status not in allowed:
        errors.append("manifest.governance.privacy_review_status no está permitido")
    limitations = governance.get("known_limitations")
    if not isinstance(limitations, list):
        errors.append("manifest.governance.known_limitations debe ser una lista")
    else:
        for index, limitation in enumerate(limitations):
            _required_text(
                limitation,
                f"manifest.governance.known_limitations[{index}]",
                errors,
            )
    if status == "frozen" and annotation_status != "complete":
        errors.append("un dataset frozen necesita revisión de anotaciones complete")
    if status == "frozen" and privacy_status != "complete":
        errors.append("un dataset frozen necesita revisión de privacidad complete")


def validate_dataset_directory(
    root: str | Path, *, require_artifacts: bool = True
) -> DatasetValidationReport:
    """Valida el manifiesto, las muestras, las particiones y los hashes."""

    dataset_root = Path(root)
    errors: list[str] = []
    manifest_path = dataset_root / "manifest.json"
    manifest = _load_json(manifest_path, errors)
    dataset_id, status = _validate_manifest_identity(dataset_root, manifest, errors)
    class_names = _validate_task(manifest, errors)
    negative_categories = _validate_selection(manifest, errors)
    source_trips = _validate_sources(manifest, errors)
    trip_to_split, declared_split_counts = _validate_splits(
        manifest, source_trips, errors
    )
    _validate_governance(manifest, status, errors)

    files = manifest.get("files")
    if not isinstance(files, dict):
        errors.append("manifest.files debe ser un objeto")
        files = {}
    sample_index = files.get("sample_index")
    if not isinstance(sample_index, dict):
        errors.append("manifest.files.sample_index debe ser un objeto")
        sample_index = {}
    index_relative = _relative_path(
        sample_index.get("relative_path"),
        "manifest.files.sample_index.relative_path",
        errors,
    )
    if index_relative != PurePosixPath("samples.jsonl"):
        errors.append("manifest.files.sample_index.relative_path debe ser samples.jsonl")
    if sample_index.get("format") != "application/x-ndjson":
        errors.append("manifest.files.sample_index.format debe ser application/x-ndjson")
    expected_index_hash = _hash_text(
        sample_index.get("sha256"), "manifest.files.sample_index.sha256", errors
    )
    index_path = dataset_root / "samples.jsonl"
    records = _load_jsonl(index_path, errors)
    if index_path.is_file() and expected_index_hash is not None:
        if _sha256(index_path) != expected_index_hash:
            errors.append("manifest.files.sample_index.sha256 no coincide con samples.jsonl")
    declared_record_count = _integer(
        sample_index.get("record_count"),
        "manifest.files.sample_index.record_count",
        errors,
    )
    if declared_record_count is not None and declared_record_count != len(records):
        errors.append("manifest.files.sample_index.record_count no coincide con samples.jsonl")

    effective_require_artifacts = require_artifacts or status == "frozen"
    seen_sample_ids: set[str] = set()
    seen_paths: set[PurePosixPath] = set()
    split_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    positive_count = 0
    negative_count = 0
    annotation_count = 0
    for line_number, record in enumerate(records, start=1):
        split, is_negative, objects, sample_class_counts = _validate_sample(
            record,
            line_number,
            index_path,
            dataset_root,
            dataset_id,
            class_names,
            negative_categories,
            source_trips,
            trip_to_split,
            effective_require_artifacts,
            seen_sample_ids,
            seen_paths,
            errors,
        )
        if split is not None:
            split_counts[split] += 1
        if is_negative is True:
            negative_count += 1
        elif is_negative is False:
            positive_count += 1
        annotation_count += objects
        class_counts.update(sample_class_counts)

    _validate_statistics(
        manifest,
        len(records),
        positive_count,
        negative_count,
        annotation_count,
        split_counts,
        class_counts,
        declared_split_counts,
        class_names,
        errors,
    )
    if errors:
        raise DatasetValidationError(errors)
    return DatasetValidationReport(
        dataset_id=dataset_id,
        sample_count=len(records),
        positive_sample_count=positive_count,
        negative_sample_count=negative_count,
        annotation_count=annotation_count,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Valida el manifiesto y las muestras de una versión del dataset."
    )
    parser.add_argument("root", type=Path, help="Carpeta raíz de la versión")
    parser.add_argument(
        "--allow-missing-artifacts",
        action="store_true",
        help="Valida el contrato sin exigir imágenes ni etiquetas; útil para el ejemplo.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = validate_dataset_directory(
            args.root, require_artifacts=not args.allow_missing_artifacts
        )
    except DatasetValidationError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(
        f"Dataset {report.dataset_id} válido: {report.sample_count} muestra(s), "
        f"{report.positive_sample_count} positiva(s), "
        f"{report.negative_sample_count} negativa(s) y "
        f"{report.annotation_count} anotación(es)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
