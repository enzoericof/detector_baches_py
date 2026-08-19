# Datos

Los videos, imágenes, pesos y datasets no se almacenan directamente en Git.

Este directorio contendrá únicamente manifiestos reproducibles y documentación. Los datos locales deberán organizarse fuera del control de versiones en:

```text
data/raw/        Capturas originales, inmutables
data/interim/    Cuadros extraídos y datos en preparación
data/processed/  Dataset listo para experimentos
data/external/   Fuentes externas como RDD2022
```

Cada versión del dataset registra origen, fecha, recorrido, criterio de selección, anotaciones, partición e integridad mediante `manifest.json` y `samples.jsonl`. El contrato completo está en [el formato del manifiesto](../docs/dataset_manifest.md).

Las capturas crudas se agrupan por jornada y recorrido. Su estructura, formatos y reglas de sincronización se definen en [el protocolo de registro de video, tiempo y GNSS](../docs/synchronization_protocol.md).
