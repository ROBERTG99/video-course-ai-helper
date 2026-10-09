Argumento: `$ARGUMENTS` = slug del curso (arqui|negsoft|dbpt|isa2). Cargá el skill `vch-pipeline` primero. Hasta que Task 14 del plan esté ✅ en PROGRESS.md, este comando es la rutina objetivo; si falta una etapa del CLI, decilo y parás.
1. `uv run python -m pipeline fetch --course $ARGUMENTS` (incremental: solo clases nuevas). Si no hay nuevas, decirlo y terminar.
2. `uv run python -m pipeline transcript --course $ARGUMENTS && uv run python -m pipeline frames --course $ARGUMENTS`.
3. Por cada clase nueva (`status`): `uv run python -m pipeline analyze --course $ARGUMENTS --class <id> --runner claude-p --budget 3`. Si `claude -p` no está disponible o falla, `--runner agent` y despachar `analista-clase` con el prompt.
4. `validate` → si falla, corregir con el analista (1 vez) → prompt de avisos y despachar `verificador-avisos` (opus) → aplicar faltantes → `integrate` → `canvas` → `sync`.
5. Reportar: ruta de la nota, avisos nuevos (copiar la sección ⚠️), costo (`state`), y si algo quedó `blocked`, el error exacto. Actualizar `_meta/PROGRESS.md`.
