# Persistencia de resultados experimentales

**Versión:** 0.1

**Estado:** piloto

## Objetivo

Conservar fuera del entorno temporal de Colab los archivos necesarios para
auditar una ejecución. Cada entrenamiento guarda sus resultados en una carpeta
propia dentro de la versión del experimento en Google Drive.

La tarea valida la persistencia y la trazabilidad. No convierte las métricas de
datos sintéticos en resultados científicos ni publica un modelo para producción.

## Destino del piloto

```text
Mi unidad/TESIS/experiments/experiment-pilot-v0.1/
  runs/
    <run_id>/
      artifact_manifest.json
      _SUCCESS.json
      config/
        args.yaml
        dataset.yaml
        experiment_config.json
        environment.json
      metrics/
        results.csv
        task10_summary.json
      plots/
        results.png
      weights/
        best.pt
        last.pt
```

Un `run_id` combina el nombre del experimento, la fecha y hora UTC y los siete
primeros caracteres de la revisión del código. Ejemplo:

```text
task10-minimum-gpu-training-20260821t153000z-9cc6210
```

Cada nueva ejecución usa otra carpeta. Los resultados anteriores no se
sobrescriben.

## Evidencia de validación

La ejecución completa del 21 de agosto de 2026 se verificó primero dentro de
Colab y luego mediante una lectura independiente de Google Drive:

- carpeta: [`task10-minimum-gpu-training-20260821t115217z-c4282d2`](https://drive.google.com/drive/folders/1VpZch8LqFW7oqgWpoUQO5JRSvbxvCLoz);
- artefactos declarados: 9;
- tamaño total: 10.836.483 bytes;
- estado de `_SUCCESS.json`: `complete`;
- SHA-256 del manifiesto: `3c313a7ce957657d5fd3fafd49267807dab5c523b9a6513c24f324b790daf4d5`.

Esta evidencia confirma que la infraestructura guarda y recupera resultados;
no evalúa la capacidad del modelo para detectar baches reales.

## Proceso de escritura

1. El notebook monta Google Drive mediante la autorización interactiva de Colab.
2. Prepara todos los archivos dentro de una carpeta `.tmp-<run_id>`.
3. Calcula tamaño y SHA-256 de cada copia.
4. Escribe `artifact_manifest.json` con contexto, rutas y huellas.
5. Escribe `_SUCCESS.json` con la huella del manifiesto.
6. Renombra la carpeta temporal a `<run_id>`.
7. Vuelve a leer la ejecución final y verifica todas las huellas.

Si la sesión se interrumpe antes del paso 6, no existe una carpeta final que
parezca completa. Una carpeta final solo se reutiliza cuando su manifiesto y
todos sus artefactos siguen siendo válidos.

## Artefactos mínimos

| Artefacto | Propósito |
|---|---|
| `best.pt` | Pesos con el mejor criterio interno de la ejecución |
| `last.pt` | Pesos al finalizar la última época |
| `results.csv` | Métricas por época |
| `results.png` | Curvas producidas por el entrenador |
| `args.yaml` | Parámetros efectivos de Ultralytics |
| `dataset.yaml` | Definición del dataset utilizado |
| `experiment_config.json` | Parámetros fijados por el notebook |
| `environment.json` | Python, PyTorch, CUDA y GPU observados |
| `task10_summary.json` | Resumen y alcance de la prueba |

`artifact_manifest.json` sigue el contrato
[`experiment_artifact_manifest.schema.json`](../schemas/experiment_artifact_manifest.schema.json).

## Verificación y recuperación

Una ejecución es aceptable solamente cuando:

- existe `_SUCCESS.json`;
- la huella del manifiesto coincide con la marca de éxito;
- todos los archivos declarados existen;
- tamaños y SHA-256 coinciden;
- el `run_id` coincide con el nombre de la carpeta.

Si una verificación falla, los archivos no deben utilizarse como evidencia ni
como entrada de otro experimento. Se conserva la carpeta para diagnóstico y se
genera una nueva ejecución después de corregir la causa.
