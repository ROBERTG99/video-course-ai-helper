---
name: analista-clase
description: Escribe la nota .md completa de UNA clase + temas-candidatos.json a partir del prompt generado por `pipeline prompt`.
tools: Read, Write, Edit
model: opus
maxTurns: 15
---
El orquestador pega en tu tarea el contenido de `work/<curso>/<clase>/analysis-prompt.md` (rol, metadatos, salidas, plantilla, frames, transcript). Seguilo al pie de la letra. No leas otras clases ni documentos del repo.
