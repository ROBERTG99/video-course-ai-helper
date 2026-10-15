# PROGRESS — Video Course AI Helper
Última actualización: 2026-10-09 (sesión de ejecución)

## Estado por fase
- F0 Bootstrap: ✅ 2026-10-09 — repo GitHub privado, `.env`, ffmpeg 9 + tesseract spa, `uv sync`, Task 1 (config/state + tests) verde, plan de implementación escrito, skill `vch-pipeline`, agentes, comandos. Retrieval verificado en arqui (`es-x-autogen` vía `player_embed_url` firmada). Inventario: arqui 15 · negsoft 7 · dbpt 8 · isa2 15 = 45 clases.
- Ola 1 (T2–T5): ✅ 2026-10-09 — vimeo/naming, vtt, frames+ocr, note_validate. Fixes al plan: `vtt.paragraphs` corta antes de agregar el cue; `frames.export` cae a `t` si el punto medio excede el video.
- Ola 2 (T6–T9): ✅ 2026-10-09 — fetch (prefiere `es-x-autogen`, paths relativos a ROOT), avisos+prompt_builder+runner, integrate+canvas, sync (no borra en Drive; falla si falta vault).
- Ola 3 (T10–T11): ✅ 2026-10-09 — CLI 12 comandos (55 tests verdes); prompts/agentes. `validate` acepta slugs de temas-candidatos.json (temas se crean en integrate); `analyze --runner agent` marca ok si nota+temas existen.
- VTT + transcript: ✅ 45/45 (arqui 15 · negsoft 7 · dbpt 8 · isa2 15). 5 clases traen solo `en-x-autogen` con texto en español (dbpt 01, 05 · isa2 04, 05, 09): se usan.
- Task 12 pilot (arqui 2026-08-17-clase-01): ✅ técnico 2026-10-09 — 163 segmentos / 43 frames (sin cámara), nota 5.7k palabras, validate OK, verificador opus: 8 faltantes · 1 corrección · 7 ambiguos → aplicados; 22 temas, MOC con outline, canvas 22 nodos file. ⏳ Revisión de Robert pendiente (abrir `vault/` en Obsidian).
  Ajustes del pilot: `avisos-prompt` en el CLI; links `Relacionado` resueltos a slugs reales; el prompt del analista lista los temas existentes del curso (reuso de slugs); fetch HLS con fragmentos concurrentes (~3 MB/s).
- Task 13 tandas: ✅ 2026-10-09 — 45/45 clases con las 7 etapas `ok` (fetch → sync); avisos verificados por opus en las 45 y aplicados.
  - arqui 15 · 161 temas (2 duplicados fusionados) · canvas 198 nodos → `ArqSoft/notas/`
  - negsoft 7 · 91 temas (4 fusionados) · canvas 128 → `NegSoft/notas/`
  - dbpt 8 · 112 temas · canvas 139 → `DBPT/notas/`
  - isa2 15 · 167 temas · canvas 198 → `ISA2/notas/`
  - Crudo (≈19 GB) en `_clases-dump/<curso>/<clase>/`; `video_path` de cada nota apunta ahí. `calendario.md` con 48 líneas fechadas.
  - Orden: arqui → negsoft → dbpt → isa2 (Robert no fijó prioridad). Costo: corridas como agentes en sesión (no hay `cost_usd` por clase).
- Task 14 rutina `/nueva-clase`: ✅ 2026-10-09 — comando reescrito con el flujo real (fetch → transcript/frames → analyze → validate → avisos-prompt + verificador → integrate/canvas/sync); CLAUDE.md y skill actualizados. ⏳ Sin probar con un video nuevo real (no hay clase nueva publicada todavía).

## Bloqueos
- Ninguno.

## Herramientas agregadas en ejecución
- CLI: `avisos-prompt`, `merge-temas a=b ...`; `integrate` re-apunta links fantasma (`relink_dangling`); `sync` re-apunta `video_path` al dump.

## Próximo paso
1. Robert: abrir `vault/` como bóveda en Obsidian y revisar el pilot (`vault/arqui/clases/2026-08-17-clase-01.md`) + 1 nota por curso. Ajustes de plantilla/prompts → DECISIONES.md → re-correr con `--force`.
2. Próxima clase publicada: `/nueva-clase <curso>` (primera prueba real de la rutina).

## Reorganización por unidades ✅ (2026-10-09 → 2026-10-15)
- Notas de clase sin timestamps; 29 documentos de unidad (opus); MOC = índice; canvas por unidades; `00-MOC-2026.md` y `calendario.md` también en Drive (`2026/`).
- Nombres de nota únicos `<curso>-<class_id>.md` (`rename-notes`): había 7 class_id repetidos entre cursos → 165 links ambiguos; ahora 0 links rotos en todo el vault. 98 tests verdes.

## Clases nuevas 2026-10-15 ✅
- arqui 16 (10/12) y 17 (10/14) · negsoft 08 (10/13) · dbpt 09 (10/14) · isa2 16 (10/12): fetch → transcript → frames → nota (opus) → validate → avisos verificados y aplicados → temas asignados a unidades → unidades actualizadas (arqui 01/05/06, negsoft 03, dbpt 06, isa2 02/09) → units-finish → sync.
- Total: 50 clases con las 7 etapas `ok` (arqui 17 · negsoft 8 · dbpt 9 · isa2 16).

## Pendiente
- Commits y push hechos (2026-10-15). Registro de clases + `/procesar-nuevas` + `scripts/procesar-nuevas.sh` ✅ (probado: sin pendientes, 0 tokens). Pendiente: decidir si se programa el script (LaunchAgent diario, ejemplo en `docs/AUTOMATIZACION.md`).
