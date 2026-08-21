# Arquitectura incremental

## Regla de integración

Cada fase debe consumir el contrato estable de la fase anterior y conservar una ejecución completa de referencia. Los componentes nuevos enriquecen la tubería; no crean demostraciones aisladas.

## Niveles del dominio

1. `CaptureSession`: jornada operativa que agrupa uno o más recorridos de un dispositivo.
2. `Trip`: una pasada por una ruta y sentido; puede contener varios segmentos de video.
3. `Detection`: predicción del detector en un cuadro de video.
4. `Observation`: detecciones del mismo bache consolidadas dentro de un recorrido.
5. `Pothole`: observaciones compatibles agrupadas entre recorridos.

Una ausencia de observación no implica que un bache haya sido reparado.

Video, GNSS y eventos de un recorrido comparten un reloj monotónico. La relación periódica de ese reloj con UTC y la estructura de archivos se definen en [el protocolo de sincronización](synchronization_protocol.md).

## Flujo previsto

```text
Capture
  -> Detection
  -> Tracking
  -> Observation
  -> GNSS synchronization
  -> Road segment matching
  -> Cross-trip association
  -> Pothole
  -> API and dashboard
```

## Versionado experimental

Cada resultado deberá identificar como mínimo:

- versión del dataset;
- versión del modelo;
- configuración de inferencia;
- versión del contrato;
- dispositivo y condiciones de captura;
- revisión del código.

La versión inicial del contrato es `0.1.0`. Los archivos en `examples/` son sintéticos y solo comprueban la integración.

Cada versión de datos procesados usa un [manifiesto reproducible](dataset_manifest.md). La partición se realiza por `trip_id`, no por cuadro, para impedir que imágenes casi consecutivas de un mismo recorrido aparezcan a ambos lados de una evaluación.

Los experimentos ejecutables viven en `notebooks/`. Cada notebook debe fijar una revisión exacta del repositorio, mostrar sus parámetros y ejecutarse de principio a fin antes de publicarse. El primer [smoke test reproducible](../notebooks/01_reproducible_smoke_test.ipynb) valida el entorno sin entrenar un modelo.

El [entrenamiento mínimo con GPU](../notebooks/02_minimum_gpu_training.ipynb)
es una prueba de infraestructura separada de los experimentos científicos.
Exige CUDA, usa datos sintéticos acotados y comprueba que el entrenador modifica
los parámetros y genera pesos, resultados y gráficas. Sus métricas no se usan
para evaluar la hipótesis de la tesis.

Los artefactos de cada ejecución se conservan según el
[protocolo de persistencia experimental](experiment_artifacts.md). La escritura
usa una carpeta temporal, huellas SHA-256 y una marca `_SUCCESS.json` para que
una interrupción no produzca una ejecución aparentemente completa.
