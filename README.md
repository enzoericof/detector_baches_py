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

## Alcance inicial

El primer prototipo se limita a cámara RGB, vías urbanas asfaltadas, condiciones diurnas, un celular Android fijo y una clase positiva (`pothole`). Profundidad, severidad técnica, costos de reparación, iOS y operación nocturna quedan fuera del alcance inicial.
