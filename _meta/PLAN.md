# PLAN — Video Course AI Helper
Diseño completo (opciones y decisiones): `docs/superpowers/specs/2026-10-09-pipeline-clases-design.md`. Este archivo = fases, checkpoints y presupuesto.

## F0 · Bootstrap y tooling (sesión Sonnet) — checkpoint: `uv run pytest` verde con tests vacíos
- [ ] `brew install ffmpeg` · `uv init` + deps: `yt-dlp imagehash pillow opencv-python-headless pytesseract webvtt-py pyyaml typer rich` · dev: `pytest ruff`
- [x] `.env` con URLs/passwords · validar con `yt-dlp --video-password ... --list-subs <url>` en 1 clase por curso → anotar en DECISIONES qué `lang` expone cada curso (esperado `es-x-autogen`)
- [x] Obsidian instalado · [ ] abrir `vault/` como bóveda · `.obsidian/` mínimo commiteado
- [ ] Repo GitHub privado `ROBERTG99/video-course-ai-helper` + commit inicial · `/clear` + `/retomar`

## F1 · Retrieval (script + 1 corrida por curso) — checkpoint: `raw/` con video+vtt+info.json de TODAS las clases, `state` fetch ✅
- [ ] `pipeline/fetch.py` (yt-dlp wrapper, `--download-archive`, nombre `YYYY-MM-DD-clase-NN` desde `upload_date`+orden)
- [ ] `pipeline/transcript.py` + tests (VTT→md; sin VTT = BLOQUEADO)
- [ ] Correr fetch para los 4 cursos (una por una, en background; son GB) · inventario haiku: tabla clases × curso × duración × ¿tiene VTT?
- [ ] Mover videos ya bajados a Drive `_clases-dump` para liberar disco si hace falta

## F2 · Pilot end-to-end (1 clase de arqui) — checkpoint: nota aprobada por Robert
- [ ] `pipeline/frames.py` + tests · tunear `sample_every_seconds`, `phash_distance_same`, crop de speaker
- [ ] `vault/_templates/clase.md` final · `prompts/analista-clase.md` · agente `analista-clase` (sonnet) sobre la clase pilot
- [ ] `verificador-avisos` (opus) sobre la misma clase · comparar · ajustar `avisos_keywords`
- [ ] Robert revisa la nota: nivel de detalle, imágenes, avisos. Decisiones → DECISIONES.md. **Nada se escala antes de este ok.**
- [ ] `/clear` + `/retomar`

## F3 · Tandas (todas las clases) — tope 4 subagentes simultáneos, tandas de 4 clases, reportar a la mitad
- [ ] Orden: curso con parcial/entrega más cercana primero (Robert define)
- [ ] Por tanda: frames (script, local) → analista-clase ×4 (sonnet) → validate mecánico → PROGRESS.md
- [ ] Verificador-avisos (opus) corre por curso al terminar sus clases, no por clase (ahorra arranques)
- [ ] Presupuesto estimado: ~60 clases × (Sonnet ~$0.3 + vision ~$0.1 + Opus prorrateado ~$0.3) ≈ $45–60 equiv. API. Alarma si una tanda de 4 supera $5.

## F4 · Integración del vault — checkpoint: `validate` sin errores en los 4 cursos
- [ ] `pipeline/integrate.py`: merge de temas candidatos → `temas/` (sonnet `integrador-vault`, conflictos a opus), MOC por curso, `avisos-<curso>.md`, `calendario.md`
- [ ] `MOC-<curso>.canvas` generado desde el MOC
- [ ] Robert navega el vault 20 min y anota qué falta

## F5 · Sync y rutina semanal — checkpoint: `/nueva-clase` funciona de punta a punta en una clase nueva
- [ ] `pipeline/sync.py` (crudo → `_clases-dump`, vault → `2026/<Curso>/clases/`)
- [ ] `.claude/commands/nueva-clase.md`: fetch incremental del curso → frames → analyze (`claude -p` con `--max-budget-usd 3`) → validate → integrate → sync
- [ ] Documentar en CLAUDE.md la rutina: "después de cada clase: `/nueva-clase <curso>`"

## Política de modelos para este proyecto
- Sesión principal: **Sonnet** (F0, F1, F3, F5). Opus/Fable solo para F2 (arbitrar plantilla/prompts) y F4 (merge de temas).
- Agentes: `analista-clase` sonnet · `clasificador-frames` sonnet (vision) · `integrador-vault` sonnet · `verificador-avisos` **opus** · `inventario` haiku.
