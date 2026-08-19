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
