# DECISIONES — Video Course AI Helper

## 2026-10-09 · Diseño inicial (ver spec para opciones descartadas)
- **Repo activo en `~/dev/video-course-ai-helper`** (GitHub privado `ROBERTG99/video-course-ai-helper`; nombre con guiones porque GitHub y las rutas no aceptan espacios; título visible "Video Course AI Helper"), Drive solo destino final + backup crudo. Por qué: patrón BD2 + playbook §1.7 (Drive causa errores de edición y git).
- **Transcript = VTT de Vimeo vía yt-dlp (`text_tracks` del player config)**. **Sin Whisper ni ASR local** (decisión de Robert): una clase sin track se reporta como BLOQUEADO. Por qué: Vimeo ya genera `es-x-autogen`; no vale mantener un segundo camino.
- **Frames = pipeline propio (ffmpeg + pHash + vision + OCR)**, no tools de terceros. Por qué: control del formato y alineación con timestamps; los tools existentes no integran con el estado por clase.
- **Análisis = subagentes en sesión para pilot/tandas; `claude -p` para la rutina semanal.** Por qué: desde 2026-06-15 `claude -p` consume crédito SDK separado; conviene gastar el interactivo en las tandas grandes y el SDK en 1 clase/semana.
- **Opus solo en `verificador-avisos` e integración de temas.** Por qué: playbook §3; el único lugar donde el recall vale el costo es en lo que el profesor dijo sobre exámenes/entregas.
- **Imágenes con link markdown relativo, notas con wikilink.** Por qué: las imágenes deben verse también en Drive/otros viewers; los wikilinks son lo que arma el grafo.
- **Plantilla de nota fija antes de cualquier fan-out** (§4.6 playbook). Cambios de plantilla = nueva decisión + re-corrida explícita.
- **Videos solo en `_clases-dump`** (no duplicados en la carpeta del curso); la nota lleva `video_path`. Por qué: ~40 GB, duplicarlos no aporta.
