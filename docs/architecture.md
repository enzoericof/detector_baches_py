# Arquitectura incremental

## Regla de integración

Cada fase debe consumir el contrato estable de la fase anterior y conservar una ejecución completa de referencia. Los componentes nuevos enriquecen la tubería; no crean demostraciones aisladas.

## Niveles del dominio

1. `Detection`: predicción del detector en un cuadro de video.
2. `Observation`: detecciones del mismo bache consolidadas dentro de un viaje.
3. `Pothole`: observaciones compatibles agrupadas entre viajes.

Una ausencia de observación no implica que un bache haya sido reparado.

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
