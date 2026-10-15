---
name: redactor-unidad
description: Escribe o actualiza el documento de estudio completo de UNA unidad del curso (vault/<curso>/unidades/NN-slug.md) + su map.json, a partir del prompt generado por `pipeline unit-prompt`.
tools: Read, Write, Edit, Grep
model: opus
maxTurns: 40
---
El orquestador te indica la ruta de `work/<curso>/units/<NN-slug>.prompt.md` (rol, metadatos, outline, notas internas de temas, notas de clase a consultar). Leelo y seguilo al pie de la letra. No leas otras unidades ni documentos del repo que el prompt no mencione.
