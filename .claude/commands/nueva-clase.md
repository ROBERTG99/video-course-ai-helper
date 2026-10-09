Argumentos: `<curso>` (arqui|negsoft|dbpt|isa2). Rutina semanal para una clase nueva (se implementa en F5):
1. `uv run python -m pipeline fetch --course $1` (incremental; solo baja lo nuevo).
2. Para cada clase nueva en `state/`: `transcript` → `frames` → `analyze` (claude -p, `--max-budget-usd 3`) → `validate` → `integrate` → `sync`.
3. Reportar: ruta de la nota, avisos nuevos detectados, costo. Si algo queda BLOQUEADO, decirlo y parar.
