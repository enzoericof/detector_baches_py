# Detector de baches

Base experimental para una tesis sobre la viabilidad de un sistema móvil de bajo costo que detecte, registre y reidentifique baches en vías urbanas paraguayas.

El desarrollo sigue una única tubería incremental:

```text
video + GNSS
  -> detecciones por cuadro
  -> observaciones consolidadas por viaje
  -> georreferenciación
  -> baches persistentes entre viajes
  -> API, mapa e indicadores
```

La primera versión establece los contratos de datos y una demostración reproducible que transforma observaciones sintéticas en GeoJSON. Las fases posteriores reemplazarán gradualmente los datos simulados con detección, seguimiento, GNSS y asociación reales.

## Conceptos centrales

- **Detección:** caja delimitadora producida en un cuadro.
- **Observación:** consolidación de las detecciones del mismo bache durante una pasada.
- **Bache:** entidad persistente que agrupa observaciones de distintos viajes.

Estas entidades se mantienen separadas para evitar duplicados y medir correctamente cada nivel del sistema.

## Ejecutar la demostración

Requiere Python 3.11 o posterior. En PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m detector_baches examples/sample_observations.json artifacts/sample_observations.geojson
```

El comando valida las observaciones y genera un `FeatureCollection` compatible con herramientas cartográficas.

## Ejecutar las pruebas

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## Validar una captura sincronizada

El ejemplo documenta una jornada con un recorrido, dos segmentos de video, una pausa y muestras GNSS. Los MP4 no se incluyen en Git, por lo que la validación del ejemplo omite únicamente la comprobación de existencia de esos binarios:

```powershell
$env:PYTHONPATH = "src"
python -m detector_baches.capture_validation examples/session-20260819-0700-D01 --allow-missing-media
```

En una captura real se ejecuta el mismo comando sin `--allow-missing-media`.

## Validar un manifiesto de dataset

El ejemplo define procedencia, selección de cuadros, clases, particiones por recorrido, estadísticas y huellas de integridad. Como no incluye imágenes ni etiquetas, se valida así:

```powershell
$env:PYTHONPATH = "src"
python -m detector_baches.dataset_validation examples/dataset-local-v0.1 --allow-missing-artifacts
```

Una versión real se valida sin `--allow-missing-artifacts` antes de congelarla y usarla en experimentos.

## Ejecutar el primer notebook de Colab

El [notebook reproducible](notebooks/01_reproducible_smoke_test.ipynb) descarga una revisión exacta del proyecto, valida los ejemplos de captura y dataset, reconcilia sus estadísticas y ejecuta todas las pruebas. No entrena todavía un modelo ni necesita GPU.

[Abrir el notebook en Google Colab](https://colab.research.google.com/github/enzoericof/detector_baches_py/blob/main/notebooks/01_reproducible_smoke_test.ipynb)

## Ejecutar el entrenamiento mínimo con GPU

El [notebook de validación GPU](notebooks/02_minimum_gpu_training.ipynb) genera
un conjunto sintético diminuto y entrena dos épocas de un detector YOLO nano.
En Colab se debe seleccionar `Entorno de ejecución → Cambiar tipo de entorno
de ejecución → GPU T4` antes de usar `Ejecutar todo`.

[Abrir el entrenamiento mínimo en Google Colab](https://colab.research.google.com/github/enzoericof/detector_baches_py/blob/main/notebooks/02_minimum_gpu_training.ipynb)

Esta prueba exige CUDA y produce una gráfica, pesos y un resumen en el disco
temporal de Colab. Sus datos son artificiales y sus métricas no miden la calidad
del futuro detector. La copia automática de resultados a Drive se incorpora en
la tarea 11.

La copia publicada conserva una ejecución correcta en una Tesla T4: CUDA fue
confirmada, se completaron las dos épocas y se generaron ambos pesos, la tabla
de resultados y la gráfica.

## Estructura

```text
src/detector_baches/   Código de la tubería
schemas/               Contratos JSON versionados
examples/              Entradas sintéticas y pequeñas
tests/                 Pruebas automatizadas
docs/                  Decisiones de arquitectura
data/                  Política y manifiestos de datos
artifacts/             Resultados generados localmente
```

## Documentación operativa

- [Arquitectura incremental](docs/architecture.md)
- [Protocolo de montaje y captura](docs/capture_protocol.md)
- [Registro y sincronización de video, tiempo y GNSS](docs/synchronization_protocol.md)
- [Formato del manifiesto del dataset](docs/dataset_manifest.md)

## Alcance inicial

El primer prototipo se limita a cámara RGB, vías urbanas asfaltadas, condiciones diurnas, un celular Android fijo y una clase positiva (`pothole`). Profundidad, severidad técnica, costos de reparación, iOS y operación nocturna quedan fuera del alcance inicial.
