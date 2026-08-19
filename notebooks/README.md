# Notebooks reproducibles

## Primer notebook de Colab

[`01_reproducible_smoke_test.ipynb`](01_reproducible_smoke_test.ipynb) prepara una revisión exacta del repositorio y valida los contratos sintéticos de captura y dataset antes de ejecutar las pruebas automáticas.

El notebook:

- funciona en Google Colab o Jupyter local;
- fija el commit `f67005b294a0e23f7ab820c001e119a4b6e7d29a`;
- usa solamente Python estándar y el código del repositorio;
- no requiere GPU;
- no monta Google Drive;
- no descarga datasets ni entrena modelos.

Abrirlo en Colab:

```text
https://colab.research.google.com/github/enzoericof/detector_baches_py/blob/main/notebooks/01_reproducible_smoke_test.ipynb
```

## Entrenamiento mínimo con GPU

[`02_minimum_gpu_training.ipynb`](02_minimum_gpu_training.ipynb) valida la
infraestructura de entrenamiento de detección. Requiere una GPU T4 de Colab,
genera 16 imágenes sintéticas, construye un YOLO nano desde cero y entrena dos
épocas. Comprueba CUDA, cambios en los parámetros, pérdidas finitas, pesos y
gráficas.

Los datos y las métricas de esta prueba no son evidencia sobre baches reales.
Los artefactos son temporales; su guardado automático en Drive pertenece a la
tarea 11.

Abrirlo en Colab:

```text
https://colab.research.google.com/github/enzoericof/detector_baches_py/blob/main/notebooks/02_minimum_gpu_training.ipynb
```

## Regenerar y ejecutar localmente

El generador necesita `nbformat`; la ejecución necesita además `nbclient` e `ipykernel`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install nbformat nbclient ipykernel
.\.venv\Scripts\python.exe scripts/build_colab_notebook.py
.\.venv\Scripts\python.exe scripts/execute_notebook.py notebooks/01_reproducible_smoke_test.ipynb
.\.venv\Scripts\python.exe scripts/build_gpu_training_notebook.py
```

La versión entregada del primer notebook se conserva ejecutada, con salidas
acotadas. Si cambia el código que consume, debe actualizarse `PROJECT_REVISION`,
regenerarse y volver a ejecutarse de principio a fin.

El notebook de GPU solo puede validarse completamente en un entorno con CUDA.
Su estructura se comprueba localmente; la evidencia definitiva es una ejecución
completa en Colab con el resumen `status: passed`.
