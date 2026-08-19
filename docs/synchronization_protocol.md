# Protocolo de registro y sincronización de video, tiempo y GNSS

**Versión:** 0.1

**Estado:** piloto

**Alcance:** contrato local de captura; no incluye Android, backend, inferencia ni entrenamiento

## 1. Objetivo

Definir cómo guardar video, tiempo, posición y eventos de operación de manera que una captura corta pueda validarse hoy y la misma estructura pueda crecer hasta una jornada municipal de varias horas.

La unidad mínima que se sincroniza es el `trip`. La `session` permite agrupar varios recorridos sin convertir toda la jornada en un único archivo frágil. Los datos se escriben primero en el dispositivo y no necesitan conexión.

## 2. Tres niveles diferentes

| Nivel | Identificador | Significado | Momento de creación |
|---|---|---|---|
| Jornada | `session_id` | Turno de captura de un dispositivo y vehículo; contiene uno o más recorridos | Antes de salir |
| Recorrido | `trip_id` | Una pasada por una ruta y sentido; puede tener pausas y varios segmentos de video | Al iniciar cada pasada |
| Observación | `observation_id` | Un mismo bache consolidado a partir de detecciones consecutivas dentro de un recorrido | Durante el procesamiento posterior |

Una pausa o un corte automático del archivo de video no crea por sí solo otro recorrido. Un cambio de ruta, sentido o pasada sí crea otro `trip`. Un reinicio del teléfono cierra el recorrido como interrumpido; la jornada puede continuar con otro recorrido y otro `clock_epoch_id`.

La tarea actual registra jornadas y recorridos. Las observaciones continúan siendo datos derivados: siempre conservan su `trip_id` y, cuando se sincronicen, tomarán su tiempo y posición de la línea temporal definida aquí.

## 3. Identificadores y nombres

Los identificadores usan solo ASCII, no contienen espacios y no se reutilizan.

```text
session-AAAAMMDD-HHMM-DNN
trip-AAAAMMDD-HHMM-RNN-PNN
obs-<trip_id>-NNNNNN
```

Ejemplo:

```text
session-20260819-0700-D01
trip-20260819-0705-R01-P01
obs-trip-20260819-0705-R01-P01-000001
```

La fecha y hora de los identificadores corresponden a la hora local usada para operar. No son una fuente de sincronización: solo facilitan la búsqueda humana.

## 4. Referencia temporal común

### 4.1 Reloj canónico

Video, muestras GNSS y eventos usan `elapsed_realtime_ns`, un contador monotónico en nanosegundos suministrado por el mismo dispositivo. Este contador es la referencia canónica para ordenar y unir datos dentro de un `clock_epoch_id` porque no retrocede si la hora civil se corrige.

Cada época de reloj se identifica con un `clock_epoch_id`. En una implementación Android futura corresponderá al reloj monotónico desde el arranque. Un `trip` no puede atravesar dos épocas. La misma jornada sí puede contener varias si el dispositivo se reinicia.

No se usan como referencia temporal:

- la fecha de modificación de los archivos;
- la hora codificada en el nombre;
- el número de cuadro dividido por los FPS nominales;
- la hora de recepción en un servidor.

### 4.2 Relación con UTC

`session_metadata.json` guarda dos o más `sync_points` por época completa. Cada punto relaciona un valor de `elapsed_realtime_ns` con una fecha `utc_time` en RFC 3339, UTC y precisión de milisegundos, por ejemplo `2026-08-19T10:05:00.000Z`.

En el piloto se registra un punto al abrir y otro al cerrar la jornada. Para jornadas largas se agrega un punto al menos cada 15 minutos y después de cualquier corrección visible del reloj. La conversión a UTC se obtiene por interpolación lineal entre los dos puntos vecinos. Se conserva el reloj monotónico original aun cuando UTC cambie.

Cada muestra GNSS y cada evento guardan ambos valores para auditoría. La diferencia entre su UTC declarado y el estimado desde los puntos de sincronización no puede superar dos segundos.

### 4.3 Tiempo de cada cuadro

Cada segmento registra el par:

```text
first_frame_media_time_us <-> first_frame_elapsed_realtime_ns
```

El tiempo común de cualquier cuadro se calcula con su PTS real del contenedor:

```text
frame_elapsed_realtime_ns =
  first_frame_elapsed_realtime_ns
  + (frame_media_time_us - first_frame_media_time_us) * 1000
```

Esto admite video de frecuencia variable y segmentos que vuelven a comenzar su PTS en cero. Cada segmento posee su propio ancla.

## 5. Formatos

### 5.1 Metadatos

- `session_metadata.json`: JSON UTF-8 con la jornada, dispositivo, vehículo, estado, recorridos y épocas de reloj.
- `trip_metadata.json`: JSON UTF-8 con ruta, pasada, montaje, intervalo y segmentos de video.
- Los contratos están en `schemas/capture_session.schema.json` y `schemas/capture_trip.schema.json`.

Los metadatos se escriben a un archivo temporal y se renombran atómicamente. Al comenzar se usa `status: active`; al cerrar correctamente, `completed`; al recuperar un corte, `interrupted`.

### 5.2 GNSS

`gnss.jsonl` usa JSON Lines UTF-8: un objeto completo por línea, según `schemas/gnss_sample.schema.json`. JSONL permite anexar y recuperar todas las líneas completas después de un cierre inesperado.

Cada muestra conserva:

- `latitude` y `longitude` en grados WGS 84;
- `horizontal_accuracy_m` en metros;
- `speed_mps` en metros por segundo;
- `heading_deg` en grados `[0, 360)`, medidos desde el norte;
- `elapsed_realtime_ns`, `utc_time` y `clock_epoch_id`;
- identificadores de jornada, recorrido y muestra;
- `provider` para auditar el origen.

`speed_mps` y `heading_deg` son `null` cuando el proveedor no los entrega; nunca se sustituyen por cero. Una precisión grande se conserva tal como fue informada y se filtra más adelante mediante criterios de calidad.

### 5.3 Eventos

`events.jsonl` también usa JSON Lines, según `schemas/capture_event.schema.json`. Registra como mínimo inicio y cierre del recorrido y de cada segmento. Los eventos `pause_started`, `pause_ended` e `interruption_detected` preservan los huecos sin inventar continuidad.

### 5.4 Video

El piloto usa MP4/H.264. Un recorrido puede contener uno o varios archivos:

```text
<trip_id>_video_0001.mp4
<trip_id>_video_0002.mp4
```

El corte por límite de tamaño o duración crea otro segmento con PTS y ancla propios, pero mantiene el mismo `trip_id`. Los archivos originales aceptados son inmutables.

## 6. Estructura local

```text
data/raw/<session_id>/
  session_metadata.json
  mount-M01.jpg
  notes.md
  trips/
    <trip_id>/
      trip_metadata.json
      gnss.jsonl
      events.jsonl
      video/
        <trip_id>_video_0001.mp4
        <trip_id>_video_0002.mp4
```

Los nombres relativos registrados en los metadatos siempre usan `/`, aunque la copia se encuentre en Windows. No se admiten rutas absolutas ni `..`.

El ejemplo versionado está en `examples/session-20260819-0700-D01/`. No incluye los MP4 para mantener el repositorio liviano; sí contiene dos segmentos declarados, una pausa, eventos y muestras GNSS sincronizadas.

## 7. Flujo sin conexión

1. Crear la carpeta de jornada y escribir sus metadatos con `status: active`.
2. Crear el recorrido y el primer evento antes de iniciar video.
3. Anexar cada muestra GNSS y evento como una línea completa, vaciando periódicamente el búfer al almacenamiento.
4. Cerrar cada MP4 y agregar su intervalo y ancla a `trip_metadata.json`.
5. Al terminar, cerrar video, mantener cobertura GNSS, cerrar el recorrido y después la jornada.
6. Validar la carpeta local antes de copiarla o sincronizarla.
7. Transferir más adelante sin renombrar ni modificar los originales. La política de subida y backend queda fuera de esta tarea.

Para campañas extensas se crea un `trip` por pasada y se limita cada MP4 por duración o tamaño. Así una falla afecta un segmento y no toda la jornada.

## 8. Pausas, divisiones e interrupciones

- **Detención normal:** no se pausa la captura; GNSS y video continúan.
- **Pausa operativa:** se registran `pause_started` y `pause_ended`. Puede cerrarse el segmento de video y abrirse otro al reanudar.
- **División automática:** se cierra un segmento y se abre el siguiente; sus intervalos pueden ser contiguos y no requieren evento de pausa.
- **Cierre inesperado:** se conservan todas las líneas JSONL completas y los MP4 recuperables. El recorrido se marca `interrupted`; el último segmento puede ser `partial` y no tener tiempo final.
- **Reanudación tras caída de la aplicación:** si continúa el mismo reloj y la misma pasada, se abre otro segmento dentro del mismo recorrido y se registra la recuperación.
- **Reinicio del dispositivo:** se crea otra época de reloj y otro recorrido dentro de la misma jornada.

Nunca se rellena un hueco interpolando video inexistente. La interpolación GNSS posterior solo puede hacerse dentro de intervalos con muestras válidas y no a través de una pausa o interrupción sin datos.

## 9. Reglas de validación

El validador comprueba de forma conjunta:

- nombres e identificadores y su correspondencia con las carpetas;
- fechas UTC, época de reloj y orden de puntos de sincronización;
- intervalos del recorrido y segmentos ordenados, sin solapamiento;
- rutas relativas seguras y nombres secuenciales de los MP4;
- orden y unicidad de muestras GNSS y eventos;
- rangos de latitud, longitud, precisión, velocidad y rumbo;
- concordancia de jornada, recorrido y reloj en todos los registros;
- coherencia UTC–reloj monotónico con tolerancia de dos segundos;
- cobertura GNSS desde antes del primer cuadro hasta después del último en recorridos completos;
- cierre de pausas, segmentos y recorrido cuando el estado es `completed`.

Validar el ejemplo de contrato, que omite los binarios:

```powershell
$env:PYTHONPATH = "src"
python -m detector_baches.capture_validation examples/session-20260819-0700-D01 --allow-missing-media
```

Validar una captura real, incluyendo la existencia de los MP4:

```powershell
$env:PYTHONPATH = "src"
python -m detector_baches.capture_validation data/raw/session-20260819-0700-D01
```

Un error de validación no borra datos. La captura se conserva y su estado o clase de calidad se revisa según el protocolo de captura.

## 10. Límites de esta versión

Esta versión define el contrato local, el ejemplo y sus comprobaciones. No implementa captura Android, subida al backend, detección, agrupación de observaciones, interpolación GNSS productiva ni entrenamiento. Esas etapas consumirán este contrato sin cambiar los archivos originales.
