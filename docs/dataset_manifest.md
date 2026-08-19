# Formato del manifiesto del dataset

**Versión del contrato:** 0.1.0

**Estado:** piloto

**Alcance:** descripción, procedencia, partición e integridad de datasets de detección; no extrae cuadros, no anota imágenes y no entrena modelos

## 1. Objetivo

Cada versión del dataset debe poder reconstruirse y auditarse sin depender de nombres informales de carpetas. El manifiesto responde, como mínimo:

- qué versión es y de cuál deriva;
- qué recorridos y capturas aportaron datos;
- por qué se seleccionó cada cuadro;
- qué clases y formato de anotación utiliza;
- qué cuadros pertenecen a entrenamiento, validación y prueba;
- cuántos positivos, negativos y objetos contiene;
- qué archivos forman la versión y cuál es su huella SHA-256;
- qué revisión de código y revisión humana respaldan una versión congelada.

El manifiesto describe datos procesados. No modifica las capturas inmutables de `data/raw`.

## 2. Archivos del contrato

Una versión se organiza así:

```text
data/processed/<dataset_id>/
  manifest.json
  samples.jsonl
  images/
    train/
    validation/
    test/
  labels/
    train/
    validation/
    test/
```

- `manifest.json`: identidad, procedencia, clases, política de selección, particiones, estadísticas y estado de revisión.
- `samples.jsonl`: un objeto JSON por cuadro. El formato anexable permite manejar datasets grandes sin cargar un único arreglo JSON.
- `images/`: cuadros extraídos, sin transformaciones destructivas posteriores al congelamiento.
- `labels/`: un archivo YOLO por imagen; los negativos válidos tienen un archivo vacío.

Los esquemas son:

- `schemas/dataset_manifest.schema.json`;
- `schemas/dataset_sample.schema.json`.

## 3. Identidad y versiones

El piloto usa identificadores como:

```text
dataset-local-v0.1
```

`dataset_version` usa SemVer completo, por ejemplo `0.1.0`. Los dos conceptos que se versionan son distintos:

- `schema_version`: versión del formato de manifiesto;
- `dataset_version`: versión del contenido seleccionado y anotado.

Una corrección compatible del contrato incrementa `schema_version`. Agregar, quitar, mover o modificar una imagen o anotación después de congelar incrementa `dataset_version` y crea otro `dataset_id`. `parent_dataset_id` conserva la genealogía.

## 4. Estados

### `draft`

La selección, las anotaciones o la revisión todavía pueden cambiar. `frozen_at_utc` y `code_revision` pueden ser `null`. El manifiesto debe seguir siendo internamente coherente.

### `frozen`

La versión está lista para experimentos reproducibles:

- `frozen_at_utc` contiene una fecha UTC;
- `code_revision` contiene el commit de Git que produjo la versión;
- la revisión de anotaciones y privacidad está completa;
- todos los archivos existen y coinciden con sus SHA-256;
- cualquier cambio posterior crea una versión nueva.

## 5. Procedencia

Cada fuente declara un `source_id`, su tipo, licencia y recorridos. Para captura local, cada recorrido conserva `session_id`, `trip_id` y clase de calidad. Un registro de `samples.jsonl` enlaza además:

- `segment_id` del video;
- PTS original mediante `frame_media_time_us`;
- reloj común mediante `frame_elapsed_realtime_ns`.

De este modo se puede volver del cuadro al video, GNSS y eventos descritos en [el protocolo de sincronización](synchronization_protocol.md).

Las fuentes externas deben registrar nombre, versión, URL y licencia. Los datos sintéticos se identifican como `synthetic`; nunca se presentan como capturas reales.

## 6. Clases y anotaciones

La primera versión contiene una clase:

| ID | Nombre |
|---:|---|
| 0 | `pothole` |

El formato inicial es YOLO con cajas normalizadas:

```text
class_id x_center y_center width height
```

Las coordenadas pertenecen al intervalo `[0, 1]`. `annotation.object_count` y `annotation.class_counts` permiten comprobar el contenido sin interpretar imágenes durante una auditoría rápida.

Un cuadro negativo tiene:

- `is_negative: true`;
- `object_count: 0`;
- conteo de clases igual a cero;
- al menos una categoría como `shadow`, `patch`, `manhole_cover`, `crack`, `puddle` u `other`;
- archivo de etiqueta vacío.

Los negativos difíciles se conservan explícitamente para medir falsos positivos y no se confunden con cuadros sin revisar.

## 7. Selección de cuadros

`selection` documenta el criterio aplicado, el espaciamiento temporal mínimo y las categorías negativas buscadas. Cada muestra añade un `selection_reason` corto.

El manifiesto no exige que todos los cuadros de un video entren al dataset. Solo registra los seleccionados. La selección debe evitar cuadros consecutivos casi idénticos y mantener diversidad de distancia, ángulo, iluminación y tipo de vía.

## 8. Particiones sin fuga

Las particiones iniciales son `train`, `validation` y `test`. La unidad indivisible es `trip_id`:

- todos los cuadros de un recorrido pertenecen a una sola partición;
- un `trip_id` no puede repetirse entre particiones;
- la asignación se guarda explícitamente, junto con la semilla y proporciones objetivo;
- los conteos declarados deben coincidir con `samples.jsonl`.

La proporción objetivo orienta la asignación, pero puede no alcanzarse exactamente en un piloto con pocos recorridos. La partición nunca se corrige moviendo cuadros individuales de un mismo recorrido.

Si varias pasadas por una ruta son casi idénticas, la revisión puede usar un grupo más conservador que `trip_id`; esa decisión se registra en `split_policy.notes`.

## 9. Integridad

Todas las rutas son relativas a la carpeta del dataset, usan `/` y no admiten `..`.

El manifiesto guarda:

- SHA-256 de `samples.jsonl`;
- SHA-256 de cada imagen;
- SHA-256 de cada etiqueta;
- conteos totales, por partición y por clase.

El validador recalcula las huellas y estadísticas. Un hash diferente indica que la versión no es la declarada; no se actualiza silenciosamente un dataset congelado.

## 10. Ejemplo y validación

El ejemplo sintético está en `examples/dataset-local-v0.1/`. Contiene el manifiesto y seis registros distribuidos por recorrido. No incluye imágenes ni etiquetas.

Validar el ejemplo de contrato:

```powershell
$env:PYTHONPATH = "src"
python -m detector_baches.dataset_validation examples/dataset-local-v0.1 --allow-missing-artifacts
```

Validar una versión real, incluyendo imágenes, etiquetas y hashes:

```powershell
$env:PYTHONPATH = "src"
python -m detector_baches.dataset_validation data/processed/dataset-local-v0.1
```

La comprobación conjunta verifica:

- identidad, versión y estado;
- procedencia de todos los cuadros;
- unicidad de muestras y rutas;
- asignación completa por recorrido, sin fuga entre particiones;
- coherencia entre positivos, negativos, etiquetas y clases;
- conteos del índice, particiones y estadísticas;
- huellas SHA-256 del índice y los artefactos presentes;
- requisitos adicionales para congelar una versión.

## 11. Límites de esta tarea

Esta tarea define el contrato y sus validaciones. No crea todavía carpetas en Drive, extrae cuadros, selecciona el dataset piloto, genera anotaciones ni ejecuta entrenamiento. Esas tareas producirán instancias reales de este formato.
