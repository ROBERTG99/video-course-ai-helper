# Video Course AI Helper — pipeline Vimeo→transcript→frames→análisis→vault Obsidian · Python 3.14 (uv) + yt-dlp + ffmpeg + claude -p

## Idioma y formato
- Código, commits, identificadores, nombres de scripts: inglés. Notas, resúmenes, docs: español rioplatense.
- Formato de nota de clase: plantilla FIJA en `templates/clase.md` (secciones y frontmatter no se cambian sin decisión en DECISIONES.md).
- Imágenes: links markdown relativos `![](img/<class_id>/0042.jpg)`. Links: `[[<curso>-<class_id>#Sección]]` (nombre de nota de clase = `<curso>-<class_id>`, único en el vault) y `[[NN-unidad#Sección]]`. Notas de clase SIN timestamps. Vault al usuario = clases + unidades + MOC + avisos + calendario (temas atómicos solo en `work/`).

## Comandos
- Setup: `uv sync` · Lint: `uv run ruff check pipeline/` · Tests: `uv run pytest -q` (SIEMPRE antes de reportar un paso como completo)
- Pipeline: `uv run python -m pipeline <fetch|transcript|frames|analyze|integrate|validate|sync> --course <slug> [--class <id>]` · headless: `claude -p ... --max-turns 30 --max-budget-usd 5` (nunca sin techo)

## Reglas de git
- NUNCA `git add .` / `-A` — agregar solo los archivos del paso actual (hook lo bloquea).
- Commits sin co-author de Claude. Ejecutando `docs/superpowers/plans/*.md`: un commit por tarea, autorizado (2026-10-09). Fuera del plan: esperar mi "ok". `vault/`, `raw/`, `state/`, `work/`, `.env` NUNCA se commitean (resultados no van a GitHub).

## Contexto y estado
- Estado: `_meta/PROGRESS.md` (leer al iniciar; NO repetir ✅). Decisiones: `_meta/DECISIONES.md`. Plan: `_meta/PLAN.md`. Diseño: `docs/superpowers/specs/2026-10-09-pipeline-clases-design.md`.
- Para retomar tras /clear: `/retomar`. Después de cada clase nueva: abrir Claude Code en este repo y correr `/nueva-clase <curso>`.
- Qué falta procesar: `pipeline pending` (exit 3 = hay) · registro `vault/clases-registro.md` (`pipeline registry`) · todos los cursos: `/procesar-nuevas` · desatendido: `scripts/procesar-nuevas.sh` · ver `docs/AUTOMATIZACION.md`.
- Drive `My Drive/2026/<Curso>/notas/` = destino final (espejo de `vault/<curso>/`). Drive `2026/_clases-dump/` = backup crudo. No se trabaja en Drive.

## Convenciones
- Cursos (slug → carpeta Drive): arqui→ArqSoft · negsoft→NegSoft · dbpt→DBPT · isa2→ISA2. Transcript SOLO del VTT `es-x-autogen` de Vimeo, obtenido con yt-dlp sobre la `player_embed_url` firmada de la API del showcase (sin login): si una clase no trae track, queda BLOQUEADO y se reporta. Config en `config/courses.yaml`. Links/passwords SOLO en `.env` (gitignored), nunca en chat ni en archivos commiteables.
- Subagentes: máx 4 simultáneos; TODOS en opus (pedido de Robert, 2026-10-09). Contexto viaja en el prompt (o en un prompt-file por clase/unidad que solo lee ese agente).
- Pipeline idempotente: estado por clase en `state/<curso>/<clase>.json`; una etapa ✅ no se re-corre salvo `--force`.
- Entregables a disco ANTES de reportar; en chat solo rutas + resumen ≤3 líneas.
