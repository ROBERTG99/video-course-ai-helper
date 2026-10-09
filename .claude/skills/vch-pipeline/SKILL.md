---
name: vch-pipeline
description: Cómo funciona y cómo se opera el pipeline Video Course AI Helper (Vimeo → VTT → frames → nota de clase → vault Obsidian → Drive). Usar en cualquier sesión de este repo antes de tocar código, correr una clase nueva, despachar agentes o responder preguntas sobre las clases.
---

# Video Course AI Helper — skill operativo

## Qué es
Pipeline para 4 cursos (arqui, negsoft, dbpt, isa2). Por clase: baja video + VTT `es-x-autogen` de Vimeo, arma `transcript.md`, extrae frames clave (ffmpeg + pHash + OCR), genera con Claude la nota `vault/<curso>/clases/<class_id>.md` (plantilla fija, avisos del profesor con cita y timestamp), integra temas al vault (notas atómicas + MOC + canvas) y espeja a Drive. Resultados (`vault/`, `raw/`, `work/`, `state/`) NUNCA van a git.

## Fuentes de verdad (leer en este orden; no releer el spec entero salvo que haga falta)
1. `CLAUDE.md` (reglas) · 2. `_meta/PROGRESS.md` (estado) · 3. `_meta/DECISIONES.md` · 4. `docs/superpowers/plans/2026-10-09-video-course-ai-helper.md` §0 "Contratos" (rutas, formatos JSON/MD, CLI, reglas de agentes paralelos) · 5. el spec en `docs/superpowers/specs/` solo para el "por qué".

## Cursos y paths
| slug | nombre | showcase (`.env`) | carpeta Drive (`$DRIVE_ROOT/<carpeta>/notas/`) |
|---|---|---|---|
| arqui | Arquitectura de Software | `ARQUI_VIMEO_URL/_PASSWORD` | `ArqSoft` |
| negsoft | Modelos de Negocios de Software | `NEGSOFT_*` | `NegSoft` |
| dbpt | Desarrollo de Productos de Base Tecnológica | `DBPT_*` | `DBPT` |
| isa2 | Ingeniería de Software Ágil 2 | `ISA2_*` | `ISA2` |
`DRIVE_ROOT` = `/Users/robert/Library/CloudStorage/GoogleDrive-robertino.gattas@gmail.com/My Drive/2026`. Backup crudo: `$DRIVE_ROOT/_clases-dump/<curso>/<class_id>/`. Passwords solo en `.env` (gitignored); nunca en chat, logs ni commits.

## Retrieval (lo que funciona, verificado 2026-10-09)
`pipeline.vimeo.VimeoShowcase` replica el flujo del álbum: `_next/viewer` → `showcase/<id>/auth` (password) → `api.vimeo.com/albums/<id>/videos` con `_hashed_pass` → `player_embed_url` **firmada (expira ~24 h)**. yt-dlp sobre esa URL con `Referer: https://vimeo.com/` usa la ruta del player sin login y expone `es-x-autogen` (vtt). NO usar `vimeo.com/showcase/.../video/...` con yt-dlp (el API client `web` pide login). Sin VTT = clase `blocked`, no se transcribe localmente.

## Comandos
```bash
uv sync && uv run pytest -q && uv run ruff check pipeline tests      # salud del repo
uv run python -m pipeline init-vault                                   # crea la estructura base del vault
uv run python -m pipeline list-showcase --course arqui                 # qué hay y qué class_id tendría
uv run python -m pipeline fetch --course arqui [--class ID] [--subs-only] [--force]
uv run python -m pipeline transcript --course arqui [--class ID]
uv run python -m pipeline frames --course arqui [--class ID]
uv run python -m pipeline prompt --course arqui --class ID             # arma analysis-prompt.md + avisos-excerpts.md
uv run python -m pipeline analyze --course arqui --class ID --runner agent|claude-p --budget 3
uv run python -m pipeline validate --course arqui [--class ID]
uv run python -m pipeline integrate --course arqui && uv run python -m pipeline canvas --course arqui
uv run python -m pipeline sync --course arqui [--class ID]
uv run python -m pipeline status [--course arqui]
```
Cada etapa deja `ok|blocked` en `state/<curso>/<class_id>.json`; una etapa `ok` no se repite sin `--force`.

## Agentes (playbook: ≤4 simultáneos, model explícito, contexto en el prompt)
- `analista-clase` (sonnet): recibe el contenido de `work/<c>/<id>/analysis-prompt.md`; escribe la nota + `temas-candidatos.json`.
- `verificador-avisos` (opus, el único): recibe el prompt de `prompt_builder.build_avisos_prompt`; escribe `avisos-review.md`; no edita la nota.
- `integrador-vault` (sonnet): organiza el outline del MOC sobre los marcadores generados.
- `inventario` (haiku): tablas de estado.
Tandas: 4 clases → 4 analistas en paralelo → `validate` → 1 reintento → PROGRESS.md. Opus solo al cerrar cada curso.

## Clase nueva de la semana
`/nueva-clase <curso>` (ver `.claude/commands/nueva-clase.md`). Si `claude -p` no está disponible, `--runner agent` y despachar el analista a mano.

## Desarrollo
Plan por olas con DoD, código y commit por tarea en `docs/superpowers/plans/2026-10-09-video-course-ai-helper.md`. Ejecutar con `superpowers:subagent-driven-development` (sonnet implementa) respetando §0.9 (cada agente toca solo sus archivos; ruff + pytest verdes antes de commitear; `git add` explícito).
