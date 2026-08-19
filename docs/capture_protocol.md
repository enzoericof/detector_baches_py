# Protocolo de montaje y captura

**Versión:** 0.1

**Estado:** piloto

**Alcance:** recorridos urbanos diurnos para construir y validar el primer dataset local

## 1. Objetivo

Obtener videos repetibles de la vía y un registro asociado del recorrido, reduciendo variaciones provocadas por el montaje, la configuración de la cámara o el comportamiento del operador.

El protocolo prioriza dos usos de la misma captura:

1. extraer cuadros para entrenar y evaluar el detector;
2. procesar el video completo para seguimiento y georreferenciación.

## 2. Condiciones del piloto

- Vías urbanas asfaltadas.
- Horario diurno con iluminación suficiente.
- Velocidad habitual entre 30 y 50 km/h, siempre condicionada por las normas y el tránsito.
- Cámara principal trasera de un único celular Android.
- Celular fijo durante todo el recorrido.
- Una clase positiva: `pothole`.
- Entre tres y cinco recorridos iniciales de 10 a 15 minutos.
- Al menos una ruta repetida en el mismo sentido para comprobar reproducibilidad.

Las capturas nocturnas, bajo lluvia intensa, en caminos no pavimentados o realizadas con el celular en la mano quedan fuera de este piloto.

## 3. Seguridad y responsabilidades

- El conductor no puede iniciar, detener ni manipular el celular mientras conduce.
- La configuración se completa con el vehículo detenido.
- Cuando sea posible, una segunda persona actúa como operador y registra incidencias.
- El soporte no debe obstruir la visión del conductor, los controles ni los airbags.
- El recorrido no debe modificar la conducción para favorecer una detección.
- Las normas de tránsito tienen prioridad sobre cualquier requisito experimental.

## 4. Equipo mínimo

- Celular Android identificado mediante un `device_id` estable.
- Soporte rígido para parabrisas o tablero.
- Cargador para vehículo y cable asegurado.
- Espacio libre suficiente para el video y el registro GNSS.
- Paño para limpiar la lente y el parabrisas.
- Aplicación de video y aplicación de registro GNSS definidas para la campaña.

El modelo del celular, versión del sistema operativo y aplicaciones utilizadas se registran en los metadatos del viaje.

## 5. Montaje del celular

1. Colocar el soporte cerca del centro horizontal del parabrisas, preferentemente del lado del acompañante.
2. Usar orientación horizontal.
3. Seleccionar la cámara trasera principal `1×`, sin zoom digital ni lente ultra gran angular.
4. Asegurar el soporte hasta que no permita rotación o deslizamiento.
5. Orientar la cámara para que la calzada ocupe aproximadamente los dos tercios inferiores de la imagen.
6. Mantener el horizonte aproximadamente en el tercio superior.
7. Evitar que el capó ocupe más de una fracción pequeña de la imagen.
8. Comprobar que limpiaparabrisas, soporte, cable y reflejos no oculten la zona central de la calzada.
9. Tomar una fotografía del montaje desde el interior antes de la primera captura de cada configuración.
10. Registrar cualquier cambio de vehículo, soporte, posición o ángulo como una nueva `mount_version`.

La posición elegida se mantiene sin cambios entre viajes comparables. Si el soporte se mueve durante un recorrido, se registra la incidencia y el viaje se revisa antes de incorporarlo al dataset.

## 6. Configuración inicial de video

| Parámetro | Valor del piloto |
|---|---|
| Resolución | 1920 × 1080 |
| Frecuencia | 30 FPS |
| Orientación | Horizontal |
| Cámara | Trasera principal `1×` |
| Zoom | Desactivado |
| Formato preferido | MP4/H.264 |
| Audio | Desactivado, salvo necesidad documentada |
| HDR o filtros | Desactivados cuando la aplicación lo permita |

La exposición, enfoque y estabilización pueden permanecer en modo automático durante el piloto, pero su configuración no debe cambiar entre recorridos comparables. Si el celular no permite seleccionar algún parámetro, se registra el valor utilizado automáticamente.

## 7. Identificación del recorrido

Cada captura utiliza un identificador único:

```text
trip-AAAAMMDD-HHMM-RNN-PNN
```

Ejemplo:

```text
trip-20260819-0830-R01-P01
```

- `RNN`: identificador de la ruta planificada.
- `PNN`: número de pasada por esa ruta y sentido.
- Fecha y hora: hora local de Paraguay al iniciar la preparación.

Los archivos originales se organizan de esta forma:

```text
data/raw/<trip_id>/
  video.mp4
  gnss.*
  trip_metadata.json
  mount.jpg
  notes.md
```

Los archivos en `data/raw` son inmutables: no se recortan, renombran ni sobrescriben después de ser aceptados.

## 8. Lista previa a la captura

- [ ] Vehículo estacionado en un lugar seguro.
- [ ] `trip_id`, ruta y número de pasada definidos.
- [ ] Fecha y hora automáticas del celular activadas.
- [ ] Batería con al menos 70 % o cargador conectado.
- [ ] Espacio libre verificado.
- [ ] Modo no molestar activado.
- [ ] Lente y parabrisas limpios.
- [ ] Celular firmemente montado y en orientación horizontal.
- [ ] Encuadre comparado con la fotografía de referencia.
- [ ] Resolución, FPS, cámara y zoom verificados.
- [ ] Ubicación precisa activada.
- [ ] Registro GNSS iniciado antes del video.
- [ ] Vista previa revisada durante al menos 30 segundos con el vehículo detenido.
- [ ] Video iniciado antes de comenzar el movimiento.

## 9. Procedimiento durante el recorrido

1. Conducir normalmente y respetar la ruta planificada cuando las condiciones lo permitan.
2. No tocar el celular ni reajustar el soporte en movimiento.
3. El acompañante registra incidencias con una hora aproximada: desvíos, detenciones, lluvia, reflejos, soporte movido u obstrucciones.
4. No interrumpir el video por semáforos o detenciones normales.
5. Si ocurre una situación de seguridad o el soporte se desprende, priorizar la detención segura y cerrar el recorrido.

## 10. Cierre del recorrido

1. Detener el vehículo en un lugar seguro.
2. Mantener la captura aproximadamente 30 segundos con el vehículo detenido.
3. Detener primero el video y luego el registro GNSS.
4. Anotar hora final, incidencias y condiciones observadas.
5. Comprobar que el video se reproduce y tiene la duración esperada.
6. Comprobar que el registro GNSS cubre desde antes del inicio hasta después del final del video.
7. Copiar los archivos a la carpeta correspondiente sin modificar los originales.
8. Completar los metadatos y asignar una clasificación de calidad.

## 11. Metadatos mínimos

| Campo | Descripción |
|---|---|
| `trip_id` | Identificador único del recorrido |
| `route_id` | Ruta planificada |
| `pass_number` | Número de pasada y sentido |
| `device_id` | Celular utilizado |
| `vehicle_id` | Vehículo utilizado |
| `mount_version` | Configuración física del soporte |
| `started_at` / `ended_at` | Inicio y fin del recorrido |
| `video_resolution` / `video_fps` | Configuración efectiva del video |
| `weather` | Estado del tiempo |
| `road_surface` | Seca, húmeda u otra condición |
| `lighting` | Condición de iluminación |
| `operator_notes` | Incidencias y observaciones |
| `quality_class` | A, B o C según la revisión |

La estructura exacta de `trip_metadata.json` y el formato GNSS se definen en la tarea de sincronización y registro temporal.

## 12. Clasificación de calidad

### Clase A: detector y georreferenciación

- Video completo, estable, enfocado y reproducible.
- Zona vial visible durante la mayor parte del recorrido.
- Registro GNSS completo y temporalmente superpuesto al video.
- Configuración y metadatos conocidos.

### Clase B: solo detector

- Video utilizable para extraer y anotar cuadros.
- GNSS inexistente, incompleto o no sincronizable.
- La limitación está documentada.

### Clase C: rechazado

- Archivo corrupto o recorrido sin metadatos básicos.
- Cámara obstruida, orientación incorrecta o soporte con movimiento severo.
- Desenfoque, reflejo o exposición que impiden identificar consistentemente la calzada.
- Configuración desconocida o cambio no documentado durante el recorrido.

Una captura de clase B no se elimina: puede seguir siendo útil para entrenar el detector. Las capturas de clase C se conservan fuera del dataset experimental y se registra la causa del rechazo.

## 13. Criterio de finalización del piloto

La etapa de captura piloto queda completa cuando existen:

- al menos tres recorridos aceptados;
- al menos dos recorridos de clase A;
- una ruta repetida con el mismo montaje y sentido;
- variedad visible de baches y negativos difíciles;
- metadatos y fotografía de montaje para cada configuración utilizada;
- material suficiente para seleccionar entre 300 y 600 cuadros sin tomar cuadros consecutivos casi idénticos.

Después del piloto se revisan encuadre, vibración, exposición, cobertura GNSS y diversidad. Cualquier cambio al protocolo crea una nueva versión antes de capturar el dataset definitivo.
