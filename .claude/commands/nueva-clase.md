Argumento: `$ARGUMENTS` = slug del curso (arqui|negsoft|dbpt|isa2). Cargá el skill `vch-pipeline` primero. Todos los comandos son `uv run python -m pipeline <cmd> --course $ARGUMENTS ...`. Todos los agentes se despachan con `model: opus`.
1. `fetch` (incremental: solo clases nuevas, video + VTT; la URL firmada expira ~24 h, por eso lista y baja en la misma corrida). Si no hay nuevas, decirlo y terminar. Si una clase queda `blocked` (sin VTT), reportarla y seguir con las demás.
2. `transcript` y `frames` (sin `--class`: procesan todo lo pendiente).
3. Por cada clase nueva (ver `status`): `analyze --class <id>` (runner agent) → despachar `analista-clase` indicándole que lea `work/$ARGUMENTS/<id>/analysis-prompt.md` → al volver, `analyze --class <id>` otra vez para marcarlo ok. (Alternativa headless: `--runner claude-p --budget 3`.)
4. `validate --class <id>` → si hay errores, pasárselos al analista (1 reintento) y re-validar con `--force`.
5. `avisos-prompt --class <id>` → despachar `verificador-avisos` indicándole que lea `work/$ARGUMENTS/<id>/avisos-prompt.md` → si hay FALTA/CORREGIR/AMBIGUO, despachar `analista-clase` para aplicarlos SOLO en ⚠️ y Dudas, sin timestamps → `validate --class <id> --force`.
6. `integrate` → lista los temas NUEVOS. Asignar cada uno a la unidad que corresponda: `integrate --assign tema=NN-unidad` (repetible; criterio: el contenido del tema y los grupos de `work/$ARGUMENTS/units.json`).
7. Por cada unidad afectada: `unit-prompt --unit NN-unidad --update tema1,tema2` → despachar `redactor-unidad` indicándole que lea `work/$ARGUMENTS/units/NN-unidad.prompt.md` (modo actualización).
8. `units-finish` (verifica mapas, reescribe los links de las clases a las secciones de unidad, regenera MOC, canvas, avisos, calendario e índice raíz; reporta links rotos) → `sync`.
9. Reportar: ruta de la nota, avisos nuevos (copiar la sección ⚠️), unidades actualizadas y cualquier `blocked` con el error exacto. Actualizar `_meta/PROGRESS.md`.
