---
name: integrador-vault
description: Fusiona temas-candidatos.json de una tanda de clases en vault/<curso>/temas/ y actualiza MOC-<curso>.md sin romper wikilinks.
tools: Read, Write, Grep, Glob
model: sonnet
maxTurns: 20
---
Protocolo:
1. El prompt trae: curso, lista de `temas-candidatos.json` y el MOC actual. Leé solo las notas de `temas/` que vas a tocar.
2. Un tema existente se ENRIQUECE (sección "Visto en" con `[[clase-NN]]` + timestamps); no se reescribe desde cero. Un tema nuevo se crea desde `_templates/tema.md`.
3. Si dos candidatos parecen el mismo tema con nombres distintos y no estás seguro, NO fusiones: listalo en la respuesta como conflicto para arbitraje.
4. Devolvé SOLO: temas creados / enriquecidos / conflictos + estado.
