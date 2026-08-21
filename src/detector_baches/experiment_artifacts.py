"""Persistencia verificable de artefactos producidos por experimentos."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "0.1.0"
RUN_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")
MANIFEST_FILENAME = "artifact_manifest.json"
SUCCESS_FILENAME = "_SUCCESS.json"


class ArtifactPersistenceError(ValueError):
    """Indica que una ejecución no puede guardarse o validarse con seguridad."""


@dataclass(frozen=True)
class ArtifactSpec:
    """Describe un archivo fuente y su ubicación estable en la ejecución."""

    source_path: str
    destination_path: str
    role: str
    media_type: str


@dataclass(frozen=True)
class PersistenceReport:
    """Resumen de una ejecución persistida y verificada."""

    run_id: str
    run_directory: Path
    artifact_count: int
    total_bytes: int
    manifest_sha256: str
    reused_existing_run: bool


def sha256_file(path: Path) -> str:
    """Calcula SHA-256 sin cargar archivos grandes completos en memoria."""

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative_path(value: str, field_name: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ArtifactPersistenceError(
            f"{field_name} debe ser una ruta relativa normalizada: {value!r}"
        )
    if "\\" in value:
        raise ArtifactPersistenceError(
            f"{field_name} debe usar separadores '/': {value!r}"
        )
    return path


def _validate_run_id(run_id: str) -> None:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ArtifactPersistenceError(
            "run_id debe usar minúsculas, números, puntos, guiones o guiones bajos"
        )


def _write_json(path: Path, content: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(content, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _manifest_entry(
    copied_path: Path,
    destination_path: PurePosixPath,
    spec: ArtifactSpec,
) -> dict[str, Any]:
    return {
        "path": destination_path.as_posix(),
        "role": spec.role,
        "media_type": spec.media_type,
        "size_bytes": copied_path.stat().st_size,
        "sha256": sha256_file(copied_path),
    }


def validate_persisted_run(run_directory: Path) -> PersistenceReport:
    """Verifica marca de finalización, manifiesto, tamaños y huellas."""

    run_directory = Path(run_directory)
    manifest_path = run_directory / MANIFEST_FILENAME
    success_path = run_directory / SUCCESS_FILENAME
    if not manifest_path.is_file() or not success_path.is_file():
        raise ArtifactPersistenceError(
            f"La ejecución {run_directory} no tiene manifiesto o marca de éxito"
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    success = json.loads(success_path.read_text(encoding="utf-8"))
    run_id = manifest.get("run_id")
    if run_id != run_directory.name:
        raise ArtifactPersistenceError("El run_id no coincide con la carpeta final")
    _validate_run_id(run_id)

    manifest_sha256 = sha256_file(manifest_path)
    if success.get("manifest_sha256") != manifest_sha256:
        raise ArtifactPersistenceError("La huella del manifiesto no coincide")
    if success.get("status") != "complete":
        raise ArtifactPersistenceError("La ejecución no está marcada como completa")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ArtifactPersistenceError("El manifiesto debe declarar artefactos")

    total_bytes = 0
    observed_paths: set[str] = set()
    for artifact in artifacts:
        relative_path = _safe_relative_path(artifact.get("path", ""), "artifacts.path")
        normalized_path = relative_path.as_posix()
        if normalized_path in observed_paths:
            raise ArtifactPersistenceError(
                f"Ruta de artefacto duplicada: {normalized_path}"
            )
        observed_paths.add(normalized_path)

        artifact_path = run_directory.joinpath(*relative_path.parts)
        if not artifact_path.is_file():
            raise ArtifactPersistenceError(f"Falta el artefacto {normalized_path}")
        size_bytes = artifact_path.stat().st_size
        if size_bytes != artifact.get("size_bytes"):
            raise ArtifactPersistenceError(
                f"El tamaño no coincide para {normalized_path}"
            )
        if sha256_file(artifact_path) != artifact.get("sha256"):
            raise ArtifactPersistenceError(
                f"La huella SHA-256 no coincide para {normalized_path}"
            )
        total_bytes += size_bytes

    if total_bytes != manifest.get("total_bytes"):
        raise ArtifactPersistenceError("El total de bytes del manifiesto no coincide")

    return PersistenceReport(
        run_id=run_id,
        run_directory=run_directory,
        artifact_count=len(artifacts),
        total_bytes=total_bytes,
        manifest_sha256=manifest_sha256,
        reused_existing_run=False,
    )


def persist_experiment_run(
    source_root: Path,
    destination_root: Path,
    run_id: str,
    artifacts: Iterable[ArtifactSpec],
    metadata: Mapping[str, Any],
) -> PersistenceReport:
    """Copia una ejecución mediante staging y publica una marca verificable."""

    _validate_run_id(run_id)
    source_root = Path(source_root).resolve()
    destination_root = Path(destination_root)
    destination_root.mkdir(parents=True, exist_ok=True)
    final_directory = destination_root / run_id
    staging_directory = destination_root / f".tmp-{run_id}"

    if final_directory.exists():
        report = validate_persisted_run(final_directory)
        return PersistenceReport(
            run_id=report.run_id,
            run_directory=report.run_directory,
            artifact_count=report.artifact_count,
            total_bytes=report.total_bytes,
            manifest_sha256=report.manifest_sha256,
            reused_existing_run=True,
        )

    artifact_specs = list(artifacts)
    if not artifact_specs:
        raise ArtifactPersistenceError("Debe declararse al menos un artefacto")

    destination_paths: set[str] = set()
    prepared_specs: list[tuple[ArtifactSpec, Path, PurePosixPath]] = []
    for spec in artifact_specs:
        source_path = _safe_relative_path(spec.source_path, "source_path")
        destination_path = _safe_relative_path(
            spec.destination_path, "destination_path"
        )
        normalized_destination = destination_path.as_posix()
        if normalized_destination in destination_paths:
            raise ArtifactPersistenceError(
                f"Destino duplicado: {normalized_destination}"
            )
        destination_paths.add(normalized_destination)

        resolved_source = source_root.joinpath(*source_path.parts).resolve()
        try:
            resolved_source.relative_to(source_root)
        except ValueError as error:
            raise ArtifactPersistenceError(
                f"La fuente sale de source_root: {spec.source_path}"
            ) from error
        if not resolved_source.is_file():
            raise ArtifactPersistenceError(
                f"No existe el artefacto requerido: {spec.source_path}"
            )
        prepared_specs.append((spec, resolved_source, destination_path))

    if staging_directory.exists():
        shutil.rmtree(staging_directory)
    staging_directory.mkdir(parents=False)

    try:
        manifest_artifacts = []
        for spec, source_path, destination_path in prepared_specs:
            copied_path = staging_directory.joinpath(*destination_path.parts)
            copied_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, copied_path)
            manifest_artifacts.append(
                _manifest_entry(copied_path, destination_path, spec)
            )

        manifest_artifacts.sort(key=lambda artifact: artifact["path"])
        total_bytes = sum(
            artifact["size_bytes"] for artifact in manifest_artifacts
        )
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "status": "complete",
            "metadata": dict(metadata),
            "artifact_count": len(manifest_artifacts),
            "total_bytes": total_bytes,
            "artifacts": manifest_artifacts,
        }
        manifest_path = staging_directory / MANIFEST_FILENAME
        _write_json(manifest_path, manifest)
        manifest_sha256 = sha256_file(manifest_path)
        _write_json(
            staging_directory / SUCCESS_FILENAME,
            {
                "schema_version": SCHEMA_VERSION,
                "run_id": run_id,
                "status": "complete",
                "manifest_sha256": manifest_sha256,
            },
        )

        staging_directory.rename(final_directory)
    except Exception:
        if staging_directory.exists():
            shutil.rmtree(staging_directory)
        raise

    return validate_persisted_run(final_directory)
