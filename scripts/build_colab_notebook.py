"""Genera el primer notebook reproducible de Google Colab."""

from __future__ import annotations

from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook


PROJECT_REVISION = "f67005b294a0e23f7ab820c001e119a4b6e7d29a"
OUTPUT_PATH = Path("notebooks/01_reproducible_smoke_test.ipynb")


def build_notebook() -> nbformat.NotebookNode:
    """Construye el notebook sin depender del estado de ejecución anterior."""

    cells = [
        new_markdown_cell(
            """# Primer entorno reproducible en Google Colab

[![Abrir en Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/enzoericof/detector_baches_py/blob/main/notebooks/01_reproducible_smoke_test.ipynb)

Este notebook comprueba que un entorno limpio puede descargar una revisión exacta del proyecto, importar el paquete, validar los contratos de captura y dataset, y ejecutar todas las pruebas automáticas.

No entrena un modelo ni monta Google Drive. Esas capacidades pertenecen a las tareas 10 y 11."""
        ),
        new_markdown_cell(
            """## Goal

Crear una ejecución pequeña, determinista y auditable que sirva como base para los experimentos posteriores de la tesis.

Al finalizar deben cumplirse cuatro condiciones:

1. el repositorio está fijado a un commit exacto;
2. el ejemplo de captura sincronizada es válido;
3. el manifiesto sintético del dataset es válido y sus estadísticas coinciden;
4. todas las pruebas del proyecto terminan correctamente."""
        ),
        new_markdown_cell(
            """## Setup

### Key Assumptions

- Python 3.11 o posterior.
- Acceso de lectura a GitHub durante la preparación.
- Los ejemplos no incluyen MP4, imágenes ni etiquetas binarias; por eso se omite únicamente su existencia.
- No se requiere GPU para esta tarea.

Los parámetros visibles de la siguiente celda identifican exactamente la ejecución."""
        ),
        new_code_cell(
            f'''from pathlib import Path
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import asdict

REPOSITORY_URL = "https://github.com/enzoericof/detector_baches_py.git"
PROJECT_REVISION = "{PROJECT_REVISION}"
RANDOM_SEED = 20260819

IS_COLAB = "COLAB_RELEASE_TAG" in os.environ
RUN_ROOT = Path("/content") if IS_COLAB else Path(tempfile.gettempdir())
PROJECT_DIR = RUN_ROOT / f"detector_baches_py_{{PROJECT_REVISION[:7]}}"

experiment_config = {{
    "repository_url": REPOSITORY_URL,
    "project_revision": PROJECT_REVISION,
    "random_seed": RANDOM_SEED,
    "runtime": "google_colab" if IS_COLAB else "local_jupyter",
}}
print(json.dumps(experiment_config, indent=2))'''
        ),
        new_markdown_cell(
            """### 1. Prepare the exact project revision

La carpeta de trabajo se crea fuera del repositorio del usuario. Si ya existe, se comprueba que apunte al remoto esperado antes de reutilizarla."""
        ),
        new_code_cell(
            '''if sys.version_info < (3, 11):
    raise RuntimeError("Este proyecto requiere Python 3.11 o posterior")

if PROJECT_DIR.exists() and not (PROJECT_DIR / ".git").is_dir():
    raise RuntimeError(f"{PROJECT_DIR} existe pero no es un clon Git válido")

if not PROJECT_DIR.exists():
    subprocess.run(
        ["git", "clone", "--filter=blob:none", "--no-checkout", REPOSITORY_URL, str(PROJECT_DIR)],
        check=True,
        text=True,
        capture_output=True,
    )
else:
    remote_url = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=PROJECT_DIR,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    if remote_url != REPOSITORY_URL:
        raise RuntimeError(f"El clon existente usa un remoto inesperado: {remote_url}")

subprocess.run(
    ["git", "fetch", "--quiet", "origin", PROJECT_REVISION],
    cwd=PROJECT_DIR,
    check=True,
)
subprocess.run(
    ["git", "checkout", "--detach", "--force", PROJECT_REVISION],
    cwd=PROJECT_DIR,
    check=True,
    text=True,
    capture_output=True,
)
actual_revision = subprocess.run(
    ["git", "rev-parse", "HEAD"],
    cwd=PROJECT_DIR,
    check=True,
    text=True,
    capture_output=True,
).stdout.strip()
assert actual_revision == PROJECT_REVISION

source_path = str(PROJECT_DIR / "src")
if source_path not in sys.path:
    sys.path.insert(0, source_path)

print(f"Revisión preparada: {actual_revision}")
print(f"Directorio preparado: {PROJECT_DIR.name}")'''
        ),
        new_markdown_cell(
            """### 2. Record the environment

La GPU se informa solo como dato de contexto. Esta ejecución no depende de ella."""
        ),
        new_code_cell(
            '''environment = {
    "python": platform.python_version(),
    "platform": platform.platform(),
    "gpu_command_available": shutil.which("nvidia-smi") is not None,
}
print(json.dumps(environment, indent=2))'''
        ),
        new_markdown_cell(
            """## Steps

### 3. Validate the synchronized capture example

Se comprueban la jornada, el recorrido, los segmentos de video, el reloj común, GNSS y eventos. Los MP4 se omiten porque el ejemplo versionado contiene solamente metadatos."""
        ),
        new_code_cell(
            '''from detector_baches.capture_validation import validate_capture_directory

capture_report = validate_capture_directory(
    PROJECT_DIR / "examples" / "session-20260819-0700-D01",
    require_media_files=False,
)
print(json.dumps(asdict(capture_report), indent=2))'''
        ),
        new_markdown_cell(
            """### 4. Validate the dataset manifest example

Se comprueban procedencia, particiones por recorrido, positivos, negativos, anotaciones, estadísticas y la huella del índice. Las imágenes y etiquetas se omiten porque son sintéticas."""
        ),
        new_code_cell(
            '''from detector_baches.dataset_validation import validate_dataset_directory

dataset_report = validate_dataset_directory(
    PROJECT_DIR / "examples" / "dataset-local-v0.1",
    require_artifacts=False,
)
print(json.dumps(asdict(dataset_report), indent=2))'''
        ),
        new_markdown_cell(
            """### 5. Reconcile the declared dataset statistics

Esta comprobación independiente vuelve a contar las líneas de `samples.jsonl` y las compara con `manifest.json`."""
        ),
        new_code_cell(
            '''dataset_root = PROJECT_DIR / "examples" / "dataset-local-v0.1"
manifest = json.loads((dataset_root / "manifest.json").read_text(encoding="utf-8"))
samples = [
    json.loads(line)
    for line in (dataset_root / "samples.jsonl").read_text(encoding="utf-8").splitlines()
]

observed_summary = {
    "sample_count": len(samples),
    "positive_sample_count": sum(not sample["is_negative"] for sample in samples),
    "negative_sample_count": sum(sample["is_negative"] for sample in samples),
    "annotation_count": sum(sample["annotation"]["object_count"] for sample in samples),
    "by_split": dict(sorted(Counter(sample["split"] for sample in samples).items())),
}
declared_statistics = manifest["statistics"]

for field in (
    "sample_count",
    "positive_sample_count",
    "negative_sample_count",
    "annotation_count",
):
    assert observed_summary[field] == declared_statistics[field]
assert observed_summary["by_split"] == declared_statistics["by_split"]

print(json.dumps(observed_summary, indent=2))'''
        ),
        new_markdown_cell(
            """### 6. Run the complete automated test suite

Las pruebas se ejecutan en un proceso limpio con el `PYTHONPATH` de la revisión fijada. La salida se limita al resumen final."""
        ),
        new_code_cell(
            '''test_environment = os.environ.copy()
test_environment["PYTHONPATH"] = str(PROJECT_DIR / "src")
test_result = subprocess.run(
    [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
    cwd=PROJECT_DIR,
    env=test_environment,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)
test_lines = test_result.stdout.strip().splitlines()
print("\\n".join(test_lines[-8:]))
if test_result.returncode != 0:
    raise RuntimeError("La batería de pruebas no terminó correctamente")'''
        ),
        new_markdown_cell(
            """## Checks

La ejecución registrada verifica:

- revisión exacta `f67005b294a0e23f7ab820c001e119a4b6e7d29a`;
- 1 recorrido, 2 segmentos, 6 muestras GNSS y 8 eventos de captura;
- 6 cuadros de dataset: 4 positivos, 2 negativos y 5 anotaciones;
- particiones de 3 cuadros de entrenamiento, 2 de validación y 1 de prueba;
- 22 pruebas automáticas correctas.

Estos resultados validan el entorno y los contratos sintéticos, no la calidad de un detector."""
        ),
        new_markdown_cell(
            """## Next Steps

1. En la tarea 10, habilitar una GPU de Colab y ejecutar un entrenamiento mínimo de prueba.
2. Mantener parámetros, semilla, revisión de código y salida visibles.
3. En la tarea 11, montar Drive y guardar resultados bajo la carpeta versionada del experimento.

No se deben presentar las métricas del futuro entrenamiento mínimo como resultados finales de la tesis."""
        ),
    ]

    return new_notebook(
        cells=cells,
        metadata={
            "colab": {
                "name": OUTPUT_PATH.name,
                "provenance": [],
            },
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.11",
            },
        },
    )


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(build_notebook(), OUTPUT_PATH)
    print(f"Notebook generado en {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
