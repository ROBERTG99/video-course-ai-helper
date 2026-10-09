# Video Course AI Helper — pipeline Vimeo→transcript→frames→análisis→vault Obsidian · Python 3.14 (uv) + yt-dlp + ffmpeg + claude -p

## Idioma y formato
- Código, commits, identificadores, nombres de scripts: inglés. Notas, resúmenes, docs: español rioplatense.
- Formato de nota de clase: plantilla FIJA en `templates/clase.md` (secciones y frontmatter no se cambian sin decisión en DECISIONES.md).
- Imágenes: links markdown relativos `![](img/clase-NN/0042.jpg)`. Notas: wikilinks `[[tema]]`.

## Comandos
- Setup: `uv sync` · Lint: `uv run ruff check pipeline/` · Tests: `uv run pytest -q` (SIEMPRE antes de reportar un paso como completo)
- Pipeline: `uv run python -m pipeline <fetch|transcript|frames|analyze|integrate|validate|sync> --course <slug> [--class <id>]` · headless: `claude -p ... --max-turns 30 --max-budget-usd 5` (nunca sin techo)

## Reglas de git
- NUNCA `git add .` / `-A` — agregar solo los archivos del paso actual (hook lo bloquea).
- Commits sin co-author de Claude. Ejecutando `docs/superpowers/plans/*.md`: un commit por tarea, autorizado (2026-10-09). Fuera del plan: esperar mi "ok". `vault/`, `raw/`, `state/`, `work/`, `.env` NUNCA se commitean (resultados no van a GitHub).

## Contexto y estado
- Estado: `_meta/PROGRESS.md` (leer al iniciar; NO repetir ✅). Decisiones: `_meta/DECISIONES.md`. Plan: `_meta/PLAN.md`. Diseño: `docs/superpowers/specs/2026-10-09-pipeline-clases-design.md`.
- Para retomar tras /clear: `/retomar`. Clase nueva de la semana: `/nueva-clase <curso> <url>`.
- Drive `My Drive/2026/<Curso>/notas/` = destino final (espejo de `vault/<curso>/`). Drive `2026/_clases-dump/` = backup crudo. No se trabaja en Drive.

## Convenciones
- Cursos (slug → carpeta Drive): arqui→ArqSoft · negsoft→NegSoft · dbpt→DBPT · isa2→ISA2. Transcript SOLO del VTT `es-x-autogen` de Vimeo, obtenido con yt-dlp sobre la `player_embed_url` firmada de la API del showcase (sin login): si una clase no trae track, queda BLOQUEADO y se reporta. Config en `config/courses.yaml`. Links/passwords SOLO en `.env` (gitignored), nunca en chat ni en archivos commiteables.
- Subagentes: máx 4 simultáneos; sonnet analiza/clasifica/integra; opus SOLO `verificador-avisos`; haiku inventaría. Contexto viaja en el prompt.
- Pipeline idempotente: estado por clase en `state/<curso>/<clase>.json`; una etapa ✅ no se re-corre salvo `--force`.
- Entregables a disco ANTES de reportar; en chat solo rutas + resumen ≤3 líneas.
