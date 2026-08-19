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

## Regenerar y ejecutar localmente

El generador necesita `nbformat`; la ejecución necesita además `nbclient` e `ipykernel`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install nbformat nbclient ipykernel
.\.venv\Scripts\python.exe scripts/build_colab_notebook.py
.\.venv\Scripts\python.exe scripts/execute_notebook.py notebooks/01_reproducible_smoke_test.ipynb
```

La versión entregada se conserva ejecutada, con salidas acotadas. Si cambia el código que consume, debe actualizarse `PROJECT_REVISION`, regenerarse y volver a ejecutarse de principio a fin.
