---
name: vch-pipeline
description: Cómo funciona y cómo se opera el pipeline Video Course AI Helper (Vimeo → VTT → frames → nota de clase → vault Obsidian → Drive). Usar en cualquier sesión de este repo antes de tocar código, correr una clase nueva, despachar agentes o responder preguntas sobre las clases.
---

# Video Course AI Helper — skill operativo

## Qué es
Pipeline para 4 cursos (arqui, negsoft, dbpt, isa2). Por clase: baja video + VTT `es-x-autogen` de Vimeo, arma `transcript.md`, extrae frames clave (ffmpeg + pHash + OCR), genera con Claude la nota `vault/<curso>/clases/<curso>-<class_id>.md` (basename único en todo el vault) (plantilla fija, SIN timestamps, avisos del profesor con cita verificados por opus). Los temas de cada clase alimentan documentos de estudio por unidad (`vault/<curso>/unidades/NN-slug.md`, uno por eje del curso) que enlazan a las secciones exactas de las clases; MOC = índice de unidades y clases; todo se espeja a Drive. Temas atómicos y outline (`work/<curso>/temas/`, `work/<curso>/units.json`) son internos. Resultados (`vault/`, `raw/`, `work/`, `state/`) NUNCA van a git.

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
uv run python -m pipeline avisos-prompt --course arqui --class ID      # arma avisos-prompt.md para verificador-avisos (opus)
uv run python -m pipeline analyze --course arqui --class ID --runner agent|claude-p --budget 3
uv run python -m pipeline validate --course arqui [--class ID]
uv run python -m pipeline integrate --course arqui [--assign tema=NN-unidad]   # temas → work/, lista temas nuevos sin unidad
uv run python -m pipeline unit-prompt --course arqui [--unit NN-slug] [--update t1,t2]   # prompt del redactor-unidad
uv run python -m pipeline units-finish --course arqui                 # chequea mapas, relinkea clases, MOC/canvas/avisos/calendario/índice raíz, links rotos
uv run python -m pipeline strip-timestamps --course arqui             # limpia [hh:mm:ss] de notas de clase
uv run python -m pipeline units-init --course arqui                   # (migración única) MOC ## Mapa → units.json + archiva temas en work/
uv run python -m pipeline sync --course arqui [--class ID]
uv run python -m pipeline status [--course arqui]
```
Cada etapa deja `ok|blocked` en `state/<curso>/<class_id>.json`; una etapa `ok` no se repite sin `--force`.

## Agentes (≤4 simultáneos; TODOS en opus por pedido de Robert; contexto en un prompt-file propio)
- `analista-clase`: lee `work/<c>/<id>/analysis-prompt.md`; escribe la nota + `temas-candidatos.json`. También aplica correcciones del verificador (solo ⚠️ y Dudas, sin timestamps).
- `verificador-avisos`: lee `work/<c>/<id>/avisos-prompt.md`; escribe `avisos-review.md`; no edita la nota. ≤3 clases por despacho.
- `redactor-unidad`: lee `work/<c>/units/<NN-slug>.prompt.md`; escribe/actualiza `vault/<c>/unidades/<NN-slug>.md` + `work/<c>/units/<NN-slug>.map.json`.
- `integrador-vault` / `inventario`: legado (outline del MOC viejo / tablas de estado).
Tandas: 4 clases → 4 analistas en paralelo → `analyze` (marca ok) → `validate` → verificadores → analista aplica revisión → `integrate` (+ `--assign`) → redactores de las unidades afectadas → `units-finish` → `sync`.

## Clase nueva de la semana
`/nueva-clase <curso>` (ver `.claude/commands/nueva-clase.md`). Si `claude -p` no está disponible, `--runner agent` y despachar el analista a mano.

## Desarrollo
Plan por olas con DoD, código y commit por tarea en `docs/superpowers/plans/2026-10-09-video-course-ai-helper.md`. Ejecutar con `superpowers:subagent-driven-development` (opus implementa) respetando §0.9 (cada agente toca solo sus archivos; ruff + pytest verdes antes de commitear; `git add` explícito).
