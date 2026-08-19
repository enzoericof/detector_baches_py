"""Genera el entrenamiento mínimo de detección para Google Colab."""

from __future__ import annotations

from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook


PROJECT_REVISION = "45cb8f28ad2b00698a33cbcca756685648bde8fa"
ULTRALYTICS_VERSION = "8.4.123"
OUTPUT_PATH = Path("notebooks/02_minimum_gpu_training.ipynb")


def build_notebook() -> nbformat.NotebookNode:
    """Construye un experimento pequeño, determinista y exclusivo para GPU."""

    cells = [
        new_markdown_cell(
            """# Entrenamiento mínimo con GPU en Google Colab

[![Abrir en Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/enzoericof/detector_baches_py/blob/main/notebooks/02_minimum_gpu_training.ipynb)

Este notebook valida que Google Colab puede entrenar un detector YOLO usando una GPU CUDA. Genera imágenes sintéticas diminutas, entrena dos épocas y presenta evidencias del dispositivo, los archivos producidos y las curvas del entrenamiento.

> **Importante:** los datos son artificiales y las métricas no representan la capacidad de detectar baches reales. Esta es una prueba de infraestructura, no un resultado experimental de la tesis."""
        ),
        new_markdown_cell(
            """## Goal

Completar una ejecución pequeña y reproducible que confirme cuatro puntos:

1. Colab asignó una GPU compatible con CUDA;
2. Ultralytics puede construir y entrenar un detector de una clase;
3. los parámetros del modelo cambian durante el entrenamiento;
4. se producen pesos, resultados tabulares y gráficas inspeccionables."""
        ),
        new_markdown_cell(
            """## Setup

### Key Assumptions

- El entorno debe configurarse con `Entorno de ejecución → Cambiar tipo de entorno de ejecución → GPU T4`.
- El conjunto sintético existe solo para comprobar la tubería de entrenamiento.
- El modelo se inicia desde cero; no descarga pesos preentrenados.
- Los resultados permanecen en el almacenamiento temporal de Colab. La persistencia en Drive corresponde a la tarea 11.

La revisión del proyecto, la versión de Ultralytics, la semilla y los parámetros quedan visibles a continuación."""
        ),
        new_code_cell(
            f'''from pathlib import Path
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile

REPOSITORY_URL = "https://github.com/enzoericof/detector_baches_py.git"
PROJECT_REVISION = "{PROJECT_REVISION}"
ULTRALYTICS_VERSION = "{ULTRALYTICS_VERSION}"
RANDOM_SEED = 20260819
IMAGE_SIZE = 256
TRAIN_IMAGE_COUNT = 12
VAL_IMAGE_COUNT = 4
EPOCHS = 2
BATCH_SIZE = 4
RUN_NAME = "task10-minimum-gpu-training"

IS_COLAB = "COLAB_RELEASE_TAG" in os.environ
RUN_ROOT = Path("/content") if IS_COLAB else Path(tempfile.gettempdir())
PROJECT_DIR = RUN_ROOT / f"detector_baches_py_{{PROJECT_REVISION[:7]}}"
WORK_DIR = RUN_ROOT / RUN_NAME

experiment_config = {{
    "purpose": "gpu_infrastructure_smoke_test",
    "repository_url": REPOSITORY_URL,
    "project_revision": PROJECT_REVISION,
    "ultralytics_version": ULTRALYTICS_VERSION,
    "random_seed": RANDOM_SEED,
    "image_size": IMAGE_SIZE,
    "train_image_count": TRAIN_IMAGE_COUNT,
    "validation_image_count": VAL_IMAGE_COUNT,
    "epochs": EPOCHS,
    "batch_size": BATCH_SIZE,
    "requested_device": "cuda:0",
    "uses_real_pothole_data": False,
}}
print(json.dumps(experiment_config, indent=2))'''
        ),
        new_markdown_cell(
            """### 1. Prepare the exact project revision

La revisión se fija para que la prueba pueda relacionarse con el estado exacto del proyecto que la definió."""
        ),
        new_code_cell(
            '''if PROJECT_DIR.exists() and not (PROJECT_DIR / ".git").is_dir():
    raise RuntimeError(f"{PROJECT_DIR} existe pero no es un clon Git válido")

if not PROJECT_DIR.exists():
    subprocess.run(
        ["git", "clone", "--filter=blob:none", "--no-checkout", REPOSITORY_URL, str(PROJECT_DIR)],
        check=True,
        text=True,
        capture_output=True,
    )

remote_url = subprocess.run(
    ["git", "remote", "get-url", "origin"],
    cwd=PROJECT_DIR,
    check=True,
    text=True,
    capture_output=True,
).stdout.strip()
if remote_url != REPOSITORY_URL:
    raise RuntimeError(f"El clon existente usa un remoto inesperado: {remote_url}")

subprocess.run(["git", "fetch", "--quiet", "origin", PROJECT_REVISION], cwd=PROJECT_DIR, check=True)
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
print(f"Revisión preparada: {actual_revision}")'''
        ),
        new_markdown_cell(
            """### 2. Install the pinned training library

La versión queda fijada para evitar que una actualización futura cambie silenciosamente esta prueba."""
        ),
        new_code_cell(
            '''subprocess.run(
    [sys.executable, "-m", "pip", "install", "--quiet", f"ultralytics=={ULTRALYTICS_VERSION}"],
    check=True,
)

import ultralytics

assert ultralytics.__version__ == ULTRALYTICS_VERSION
print(f"Ultralytics {ultralytics.__version__} preparado")'''
        ),
        new_markdown_cell(
            """### 3. Require and identify the GPU

No se permite continuar en CPU: una ejecución correcta constituye evidencia explícita de que CUDA estuvo disponible."""
        ),
        new_code_cell(
            '''import platform
import torch

if not torch.cuda.is_available():
    raise RuntimeError(
        "No hay una GPU CUDA activa. En Colab seleccioná Entorno de ejecución > "
        "Cambiar tipo de entorno de ejecución > GPU T4 y volvé a ejecutar todo."
    )

torch.manual_seed(RANDOM_SEED)
torch.cuda.manual_seed_all(RANDOM_SEED)
random.seed(RANDOM_SEED)

gpu_properties = torch.cuda.get_device_properties(0)
environment = {
    "runtime": "google_colab" if IS_COLAB else "local_jupyter",
    "python": platform.python_version(),
    "torch": torch.__version__,
    "cuda_available": torch.cuda.is_available(),
    "cuda_runtime": torch.version.cuda,
    "gpu_name": torch.cuda.get_device_name(0),
    "gpu_memory_gib": round(gpu_properties.total_memory / (1024 ** 3), 2),
}
assert environment["cuda_available"] is True
print(json.dumps(environment, indent=2))'''
        ),
        new_markdown_cell(
            """## Steps

### 4. Generate a bounded synthetic detection dataset

Las imágenes imitan solamente una calzada y una mancha oscura. Cada positivo tiene una caja YOLO normalizada y algunos cuadros son negativos. No se incluyen ni se sustituyen datos de campo."""
        ),
        new_code_cell(
            '''import math
import numpy as np
from PIL import Image, ImageDraw
import yaml

if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)

dataset_root = WORK_DIR / "synthetic_dataset"
for split in ("train", "val"):
    (dataset_root / "images" / split).mkdir(parents=True, exist_ok=True)
    (dataset_root / "labels" / split).mkdir(parents=True, exist_ok=True)


def create_synthetic_sample(split: str, index: int, positive: bool) -> dict:
    sample_seed = RANDOM_SEED + (0 if split == "train" else 10_000) + index
    generator = np.random.default_rng(sample_seed)

    base = np.zeros((IMAGE_SIZE, IMAGE_SIZE, 3), dtype=np.float32)
    vertical_gradient = np.linspace(150, 95, IMAGE_SIZE, dtype=np.float32)[:, None]
    noise = generator.normal(0, 6, (IMAGE_SIZE, IMAGE_SIZE))
    road = np.clip(vertical_gradient + noise, 0, 255)
    base[:, :, 0] = road
    base[:, :, 1] = road
    base[:, :, 2] = road * 0.98
    image = Image.fromarray(base.astype(np.uint8), mode="RGB")
    draw = ImageDraw.Draw(image)

    draw.line((70, IMAGE_SIZE, 115, 0), fill=(220, 220, 205), width=3)
    draw.line((186, IMAGE_SIZE, 141, 0), fill=(220, 220, 205), width=3)
    for y in range(20, IMAGE_SIZE, 55):
        draw.line((127, y, 127, min(y + 28, IMAGE_SIZE)), fill=(235, 225, 180), width=2)

    label_line = ""
    box = None
    if positive:
        center_x = int(generator.integers(92, 165))
        center_y = int(generator.integers(145, 215))
        width = int(generator.integers(38, 70))
        height = int(generator.integers(16, 31))
        x0, y0 = center_x - width // 2, center_y - height // 2
        x1, y1 = center_x + width // 2, center_y + height // 2
        draw.ellipse((x0, y0, x1, y1), fill=(35, 35, 32), outline=(20, 20, 18), width=2)
        draw.arc((x0 + 4, y0 + 3, x1 - 4, y1 - 2), 195, 340, fill=(80, 80, 73), width=2)
        normalized = (
            center_x / IMAGE_SIZE,
            center_y / IMAGE_SIZE,
            width / IMAGE_SIZE,
            height / IMAGE_SIZE,
        )
        label_line = "0 " + " ".join(f"{value:.6f}" for value in normalized) + "\\n"
        box = [x0, y0, x1, y1]

    stem = f"{split}-{index:03d}"
    image_path = dataset_root / "images" / split / f"{stem}.jpg"
    label_path = dataset_root / "labels" / split / f"{stem}.txt"
    image.save(image_path, quality=92)
    label_path.write_text(label_line, encoding="utf-8")
    return {"split": split, "image": image_path, "positive": positive, "box": box}


samples = []
for split, count in (("train", TRAIN_IMAGE_COUNT), ("val", VAL_IMAGE_COUNT)):
    for index in range(count):
        samples.append(create_synthetic_sample(split, index, positive=index % 4 != 0))

dataset_yaml = dataset_root / "dataset.yaml"
dataset_yaml.write_text(
    yaml.safe_dump(
        {
            "path": str(dataset_root),
            "train": "images/train",
            "val": "images/val",
            "names": {0: "pothole"},
        },
        sort_keys=False,
    ),
    encoding="utf-8",
)

dataset_summary = {
    "train_images": sum(sample["split"] == "train" for sample in samples),
    "validation_images": sum(sample["split"] == "val" for sample in samples),
    "positive_images": sum(sample["positive"] for sample in samples),
    "negative_images": sum(not sample["positive"] for sample in samples),
    "classes": ["pothole"],
}
assert dataset_summary == {
    "train_images": 12,
    "validation_images": 4,
    "positive_images": 12,
    "negative_images": 4,
    "classes": ["pothole"],
}
print(json.dumps(dataset_summary, indent=2))'''
        ),
        new_markdown_cell(
            """### 5. Inspect generated samples

La vista previa permite comprobar visualmente que las cajas coinciden con el objeto sintético y que existen negativos."""
        ),
        new_code_cell(
            '''import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

preview_samples = [samples[1], samples[2], samples[4], samples[0]]
figure, axes = plt.subplots(1, 4, figsize=(14, 3.5))
for axis, sample in zip(axes, preview_samples):
    axis.imshow(Image.open(sample["image"]))
    if sample["box"]:
        x0, y0, x1, y1 = sample["box"]
        axis.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, color="lime", linewidth=2))
    axis.set_title("positivo" if sample["positive"] else "negativo")
    axis.axis("off")
figure.suptitle("Datos sintéticos usados solo para validar la tubería", fontsize=12)
plt.tight_layout()
plt.show()'''
        ),
        new_markdown_cell(
            """### 6. Train a nano object detector for two epochs

Se crea un YOLO nano desde su configuración, sin pesos preentrenados. Un callback registra el dispositivo exacto al iniciar el entrenamiento y se conserva una copia del estado inicial para comprobar que hubo actualizaciones."""
        ),
        new_code_cell(
            '''from ultralytics import YOLO

model = YOLO("yolo26n.yaml")
initial_state = {
    name: tensor.detach().cpu().clone()
    for name, tensor in model.model.state_dict().items()
    if tensor.is_floating_point()
}
training_device_evidence = {}


def record_training_device(trainer):
    parameter = next(trainer.model.parameters())
    training_device_evidence.update(
        {"device": str(parameter.device), "is_cuda": bool(parameter.is_cuda)}
    )


model.add_callback("on_train_start", record_training_device)
training_result = model.train(
    data=str(dataset_yaml),
    epochs=EPOCHS,
    imgsz=IMAGE_SIZE,
    batch=BATCH_SIZE,
    device=0,
    workers=2,
    seed=RANDOM_SEED,
    deterministic=True,
    pretrained=False,
    optimizer="SGD",
    amp=False,
    plots=True,
    val=True,
    save=True,
    project=str(WORK_DIR / "runs"),
    name=RUN_NAME,
    exist_ok=True,
    verbose=False,
)

changed_tensor_count = sum(
    not torch.equal(initial_state[name], tensor.detach().cpu())
    for name, tensor in model.model.state_dict().items()
    if name in initial_state
)
print(json.dumps({
    "training_device": training_device_evidence,
    "changed_parameter_tensors": changed_tensor_count,
}, indent=2))'''
        ),
        new_markdown_cell(
            """## Checks

### 7. Validate the run and show its graph

La prueba exige GPU real, dos filas de resultados, pérdidas finitas, parámetros modificados y los artefactos mínimos que genera el entrenador."""
        ),
        new_code_cell(
            '''import csv
from IPython.display import Image as DisplayImage, display

save_dir = Path(training_result.save_dir)
results_csv = save_dir / "results.csv"
best_weights = save_dir / "weights" / "best.pt"
last_weights = save_dir / "weights" / "last.pt"
results_plot = save_dir / "results.png"

with results_csv.open(encoding="utf-8") as results_file:
    epoch_rows = list(csv.DictReader(results_file))

loss_columns = [
    column.strip()
    for column in epoch_rows[0]
    if column.strip().startswith("train/") and column.strip().endswith("loss")
]
loss_values = {
    column: [float(row[column]) for row in epoch_rows]
    for column in loss_columns
}

assert training_device_evidence.get("is_cuda") is True
assert training_device_evidence.get("device", "").startswith("cuda")
assert len(epoch_rows) == EPOCHS
assert loss_columns
assert all(math.isfinite(value) for values in loss_values.values() for value in values)
assert changed_tensor_count > 0
assert results_csv.is_file()
assert best_weights.is_file()
assert last_weights.is_file()
assert results_plot.is_file()

run_checks = {
    "cuda_training_confirmed": True,
    "training_device": training_device_evidence["device"],
    "completed_epochs": len(epoch_rows),
    "changed_parameter_tensors": changed_tensor_count,
    "finite_training_losses": True,
    "results_csv_created": results_csv.is_file(),
    "best_weights_created": best_weights.is_file(),
    "last_weights_created": last_weights.is_file(),
    "results_plot_created": results_plot.is_file(),
}
print(json.dumps(run_checks, indent=2))
display(DisplayImage(filename=str(results_plot), width=900))'''
        ),
        new_markdown_cell(
            """### 8. Produce an ephemeral execution summary

El resumen permite auditar la prueba dentro de la sesión actual. En esta tarea no se copia a Drive ni se declara un modelo utilizable."""
        ),
        new_code_cell(
            '''summary = {
    "status": "passed",
    "scope": "infrastructure_only",
    "experiment": experiment_config,
    "environment": environment,
    "dataset": dataset_summary,
    "checks": run_checks,
    "losses_by_epoch": loss_values,
    "artifact_directory": str(save_dir),
    "scientific_result": False,
}
summary_path = save_dir / "task10_summary.json"
summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps({
    "status": summary["status"],
    "scope": summary["scope"],
    "gpu": environment["gpu_name"],
    "epochs": run_checks["completed_epochs"],
    "summary_file": summary_path.name,
}, indent=2))'''
        ),
        new_markdown_cell(
            """## Next Steps

Una ejecución completa confirma Colab, CUDA y la tubería de entrenamiento de detección. No confirma exactitud sobre calles reales.

La tarea 11 deberá montar Google Drive y copiar automáticamente un resumen, las curvas, la configuración y los pesos a la carpeta versionada del experimento. El entrenamiento con datos reales se diseñará después de capturar, anotar y congelar un dataset válido."""
        ),
    ]

    return new_notebook(
        cells=cells,
        metadata={
            "accelerator": "GPU",
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
