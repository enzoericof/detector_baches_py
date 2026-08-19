# Datos

Los videos, imágenes, pesos y datasets no se almacenan directamente en Git.

Este directorio contendrá únicamente manifiestos reproducibles y documentación. Los datos locales deberán organizarse fuera del control de versiones en:

```text
data/raw/        Capturas originales, inmutables
data/interim/    Cuadros extraídos y datos en preparación
data/processed/  Dataset listo para experimentos
data/external/   Fuentes externas como RDD2022
```

Cada versión del dataset deberá registrar origen, fecha, viaje, criterio de selección, anotaciones y partición de entrenamiento, validación o prueba.
