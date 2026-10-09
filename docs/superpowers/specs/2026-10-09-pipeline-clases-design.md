# Video Course AI Helper — diseño: pipeline Vimeo → transcript → frames → análisis → vault Obsidian
**Fecha:** 2026-10-09 · **Estado:** borrador para aprobación de Robert · **Cursos:** arqui, negsoft, dbpt, isa2

## 1. Objetivo
Para cada clase grabada (Zoom → Vimeo, showcase con password por curso) obtener, sin transcribir a mano:
1. Video guardado (backup).
2. Transcript con timestamps (VTT de Vimeo).
3. Imágenes clave (slides, código, diagramas, demos) alineadas con el transcript.
4. Una nota `.md` por clase con análisis completo, imágenes embebidas y **avisos del profesor** (parciales, entregas, fechas, reglas, "esto va al examen").
5. Notas atómicas por tema + mapa de contenido (MOC) por curso + calendario global → vault Obsidian navegable como mapa mental.
6. Espejo por curso en Drive `2026/<Curso>/clases/` y backup crudo en Drive `2026/_clases-dump/`.

Criterio de éxito: Robert puede preguntarle a Claude Code "¿qué dijo el profe de la entrega 2 de isa2?" y la respuesta sale del vault con cita y timestamp, sin reabrir el video.

## 2. Dónde está el VTT de Vimeo (verificado contra el extractor de yt-dlp)
- El player de Vimeo expone `https://player.vimeo.com/video/<id>/config` (JSON). En `request.text_tracks[]` vienen `{lang, url, kind, label}`; los subtítulos automáticos aparecen con `lang` tipo `es-x-autogen` (provenance `ai_generated`). La `url` es relativa a `player.vimeo.com` o firmada en `captions.vimeo.com` y **expira**: hay que bajar el `.vtt` y guardarlo, no el link.
- Segunda vía (si el video expone `metadata.connections.texttracks`): `api.vimeo.com/videos/<id>/texttracks?include_transcript=true` → campo `link` por track. Requiere token del dueño; **no aplica** (los videos son del profesor).
- **Ruta verificada (2026-10-09):** la URL `vimeo.com/showcase/<id>/video/<vid>` NO sirve con yt-dlp 2026.08 (su API client `web` exige login). Lo que funciona: replicar el flujo del álbum (`_next/viewer` → `showcase/<id>/auth` con password → `api.vimeo.com/albums/<id>/videos?_hashed_pass=…`) para obtener la `player_embed_url` **firmada** (`bypass_privacy=1&h=…&s=…`, expira ~24 h) y pasársela a yt-dlp con `Referer: https://vimeo.com/`. Esa ruta usa el config del player sin login y lista `es-x-autogen` (vtt). Implementado en `pipeline/vimeo.py` + `pipeline/fetch.py` (plan §0.2).
- Fallback si Vimeo cambia el flujo: `--cookies-from-browser chrome` con el showcase abierto; último recurso: fetch directo del `/config` con la misma query firmada y parsear `text_tracks`.
- Si una clase no tiene track → la clase queda `BLOQUEADO: sin VTT` y se reporta. Decisión de Robert: no se transcribe localmente.

## 3. Opciones evaluadas por etapa (con recomendación)

### 3.1 Retrieval (video + VTT + metadata)
| Opción | Pros | Contras | Veredicto |
|---|---|---|---|
| **A. yt-dlp sobre el showcase** (`--video-password`, `--write-subs`, `--write-info-json`, `--download-archive`) | Un comando por curso, incremental, baja VTT + video + metadata (título, fecha, duración) de una | Depende de que Vimeo no cambie el player; URLs de VTT firmadas (yt-dlp las resuelve al momento) | **Recomendada** |
| B. Vimeo API oficial (`/videos/{id}/texttracks`) | Contrato estable | Necesita token del dueño del video (el profesor) | Descartada |
| C. Scrapers de terceros (Apify "vimeo-transcript-scraper", etc.) | Cero código | Pago, dependencia externa, mandan la URL del curso a un tercero | Descartada |
| D. Manual: player → menú CC → "abrir .vtt en pestaña" | Sin tooling | 60+ clases a mano | Solo para depurar un caso |

Calidad de video: `-f "bv*[height<=720]+ba/b[height<=720]"` (slides legibles, ~0.5–1 GB por clase de 3 h). Si el pilot muestra texto borroso en código, subir a 1080 solo para ese curso.

### 3.2 Transcript
| Opción | Veredicto |
|---|---|
| **VTT de Vimeo (`es-x-autogen`)** → limpiar (merge de cues solapados, párrafos de ~30 s con `[hh:mm:ss]`) | **Default**. Calidad ASR de Vimeo es suficiente para resumen; los nombres propios/siglas se corrigen con un glosario por curso (`config/glossary-<curso>.txt`) aplicado en la limpieza. |
| ASR local (Whisper / Parakeet / WhisperX) | **Descartado por decisión de Robert (2026-10-09)**: todas las clases tienen VTT en Vimeo. Si alguna no lo tuviera, se reporta y se decide a mano. |

### 3.3 Extracción de imágenes clave
| Opción | Pros | Contras | Veredicto |
|---|---|---|---|
| **A. Pipeline propio**: `ffmpeg fps=1/10` → pHash (imagehash) para colapsar frames consecutivos iguales → clasificador visual (Haiku/Sonnet vision: slide/código/diagrama/pizarra/demo/speaker) → OCR tesseract `spa+eng` → re-extraer a 1280 px solo los frames que quedan | Control total, se alinea con timestamps del VTT, descarta speaker-only, OCR da texto buscable | ~150 líneas de Python a mantener | **Recomendada** |
| B. Tools existentes: `vid2slides` (HMM, descarta caras), `AutoSlides-Extractor` (CLI, ONNX MobileNet clasifica no-slides), `meeting-slide-extractor` (2026, alinea transcript) | Ya resuelven dedupe y filtro de caras | Formatos de salida propios, mantenimiento desigual, no integran con nuestro estado por clase | Robar ideas (crop de la miniatura de Zoom, HMM de cambios); no usarlos como dependencia |
| C. PySceneDetect (`ContentDetector`) | Maduro | Diseñado para cortes de video, no para slides estáticas; ruido con la cámara del speaker | Descartada |
| D. LLM multimodal sobre el video entero (Gemini acepta video nativo) | Sin pipeline de frames | Otro proveedor, costo por minuto de video, sin control de qué frame se guarda | Descartada para v1 |

Detalle que importa para Zoom: antes de hashear, recortar la región de la miniatura del speaker (configurable por curso en `courses.yaml`) para que el movimiento de la cámara no genere "slides nuevas". Dedupe global además del consecutivo (el profe vuelve a una slide anterior): se guarda una sola imagen y la nota referencia ambos timestamps.

### 3.4 Análisis (LLM)
| Opción | Pros | Contras | Veredicto |
|---|---|---|---|
| **A. Subagentes dentro de Claude Code** (Agent tool, `model:` explícito, ≤4 simultáneos) | Usa el plan interactivo; agentes versionados en `.claude/agents/`; contexto viaja en el prompt | Orquestación manual por tanda; cada arranque ~52K tokens | **Recomendada para el pilot y las tandas** |
| B. `claude -p` headless desde `pipeline/analyze.py` (`--max-budget-usd`, `--output-format json`) | 100% scripteable y reproducible, ideal para la rutina semanal | Desde 2026-06-15 el uso de `claude -p`/Agent SDK en planes de suscripción consume un **crédito mensual separado**: verificar cuánto queda antes de una tanda de 60 clases | **Recomendada para la rutina semanal** (`/nueva-clase`) una vez estable |
| C. API Anthropic directa (Batch API, −50%) | Más barato por token, asíncrono | Pago por uso fuera del plan; otro código | Si el crédito SDK no alcanza |
| D. Modelo local (Ollama) para primer pase | Gratis | Calidad insuficiente en español técnico y en captar avisos sutiles | Descartada |

Modelos (§3 del playbook): **Sonnet** = resumen de clase, extracción de temas, clasificación de frames, integración al vault. **Opus** = SOLO verificación de avisos (recall sobre lo que dijo el profesor) y arbitraje de merges de temas. **Haiku** = inventario, limpieza, OCR triage.

Estrategia de contexto: una clase de 3 h ≈ 30–45K tokens de transcript. Entra entera en Sonnet; se pasa en **un** prompt con `frames.json` (timestamps + label + OCR) para que el análisis cite imágenes por timestamp. Si supera 120K tokens se hace map-reduce por bloques de 20 min.

### 3.5 Organización (Obsidian / "mapa mental")
| Opción | Veredicto |
|---|---|
| **Notas atómicas por tema + MOC por curso (outline anidado de wikilinks) + tags + graph view** | **Base**. Es lo que hace a Obsidian útil: cada tema es una nota, cada clase enlaza a sus temas, el MOC es el índice jerárquico. Funciona sin plugins. |
| `.canvas` generado por script desde el MOC (formato JSON abierto: nodes + edges) | **Sí, en F4**: mapa mental visual real por curso, sin depender de plugins. |
| Plugin "Canvas Mind Map" (markdown → canvas, 7 layouts) | Alternativa al script si se prefiere interactivo. |
| Plugin "Mind Map" (Markmap) / "Enhancing Mindmap" | Markmap lleva ~5 años sin updates; Enhancing es editor, no genera canvas. Opcionales para visualizar el MOC. |
| NotebookLM como capa de Q&A | Solo importa texto, pierde lo visual; además exportar el vault entero a un tercero no aporta sobre Claude Code leyendo el vault. Descartado. |

Estructura del vault (una sola bóveda, local, en el repo):
```
vault/
  00-MOC-2026.md            índice de los 4 cursos
  calendario.md             todos los avisos con fecha, ordenados (generado)
  _templates/{clase,tema}.md
  <curso>/
    MOC-<curso>.md          outline jerárquico de temas → mapa mental
    avisos-<curso>.md       avisos verificados, con cita + timestamp + link a la clase
    clases/YYYY-MM-DD-clase-NN.md
    clases/img/clase-NN/0042.jpg
    temas/<slug>.md         nota atómica; sección "Visto en" con [[clase-NN]] y timestamps
```
Mapa mental = MOC (texto) + `MOC-<curso>.canvas` (visual) + graph view. Las imágenes van con link markdown relativo (portable a Drive); las notas con wikilink.

### 3.6 Validación
1. **Mecánica (script `validate`)**: VTT existe y su duración ≈ duración del video (±2%); `frames.json` no vacío; la nota tiene todas las secciones de la plantilla; toda imagen referenciada existe; todo wikilink resuelve; frontmatter completo.
2. **Recall de avisos (opus `verificador-avisos`)**: se le dan los fragmentos del transcript que matchean `avisos_keywords` (±60 s de contexto) + la sección "Avisos" de la nota; devuelve lo que falta o está mal fechado. Esta es la parte de mayor valor y la única que justifica Opus.
3. **Humana**: Robert revisa 1 clase por curso tras el pilot (plantilla, nivel de detalle, qué imágenes sobran).

### 3.7 Ubicación y backup
| Opción | Veredicto |
|---|---|
| **Repo local `~/dev/video-course-ai-helper/` (GitHub privado: código, vault, estado) + Drive como destino final y backup crudo** | **Recomendada**: mismo patrón que BD2; el playbook §1.7 documenta ~10% de errores de edición cuando se trabaja en Drive. |
| Todo en Drive `2026/` | Simple de encontrar, pero Drive + git + archivos grandes = conflictos y archivos "online-only" que ffmpeg no puede leer. Descartada. |

Flujo de datos: `raw/<curso>/<clase>/` (local, gitignored) recibe video + vtt + info.json → se procesa → al cerrar la clase: video + vtt + frames + info.json se **mueven** a Drive `2026/_clases-dump/<curso>/<clase>/` (backup "por las dudas", fuera de las carpetas de cursos, como pidió Robert) y `vault/<curso>/` se **espeja** a Drive `2026/<Curso>/notas/` con rsync. Estimación de espacio: 4 cursos × ~15 clases × ~0.7 GB ≈ 40 GB en Drive; local solo las clases en proceso.

## 4. Componentes (cada uno con una responsabilidad)
| Módulo | Hace | Entrada → Salida |
|---|---|---|
| `pipeline/fetch.py` | yt-dlp sobre el showcase; incremental | `.env`, `courses.yaml` → `raw/<c>/<clase>/{video.mp4, *.vtt, info.json}` |
| `pipeline/transcript.py` | VTT → md limpio con `[hh:mm:ss]`, glosario, merge de cues | `*.vtt` → `transcript.md` |
| `pipeline/frames.py` | muestreo, crop, pHash, clasificación, OCR, export | `video.mp4` → `frames.json` + `img/` |
| `pipeline/analyze.py` | arma el prompt (plantilla + transcript + frames.json) y lanza Sonnet (in-session o `claude -p`) | → `clases/<clase>.md` + `temas-candidatos.json` |
| `pipeline/integrate.py` | merge de temas candidatos en `temas/`, actualiza MOC, avisos, calendario, canvas | → vault |
| `pipeline/validate.py` | checks mecánicos + lanza `verificador-avisos` | → `state/<c>/<clase>.json` |
| `pipeline/sync.py` | mueve crudo a `_clases-dump`, rsync vault → Drive | → Drive |
| `state/<c>/<clase>.json` | etapa completada, hashes, costos | idempotencia |

## 5. Plantilla de nota de clase (fija antes del fan-out)
Frontmatter: `curso, fecha, numero, titulo, duracion, vimeo_url, video_path, estado, tags`.
Secciones (en este orden, siempre presentes aunque digan "—"): Resumen ejecutivo · ⚠️ Avisos del profesor · Índice de temas (timestamp + wikilink) · Desarrollo por tema (con imágenes: `![](img/clase-NN/0042.jpg)` + "qué muestra" + `[hh:mm:ss]`) · Conceptos y definiciones · Ejemplos, demos y código · Preguntas de alumnos y respuestas · Dudas / a verificar · Citas textuales relevantes · Material referenciado.

## 6. Manejo de errores
- yt-dlp falla por password → error claro, no reintenta en loop (§6.4 del playbook). Falla por anti-bot → `--cookies-from-browser`.
- Sin VTT → `BLOQUEADO: sin VTT` en estado; se reporta, no se inventa transcript.
- Frame classifier falla → se conservan todos los frames deduplicados (sin filtro), la nota lo indica.
- Análisis excede presupuesto → la clase queda `BLOQUEADO` en estado; se reporta, no se relanza la tanda.
- Validación falla → la clase no se sincroniza a Drive hasta corregir.

## 7. Testing
`pytest` sobre: parser VTT (cues solapados, timestamps), dedupe pHash con fixtures de 10 frames, armado de prompt (tamaño, secciones), validador (nota con sección faltante, imagen rota, wikilink roto), generador de canvas (JSON válido). Los pasos con LLM se prueban con el pilot (1 clase por curso), no con tests unitarios.

## 8. Fuera de alcance (v1)
Diarización, Q&A con RAG sobre el vault (Claude Code ya lee el vault), export a Notion, PDF de resúmenes, procesamiento de slides PDF que el profesor suba aparte (se puede agregar como insumo en F5).

## 9. Resueltas por Robert (2026-10-09)
1. URLs + passwords cargados en `.env` (gitignored). 2. Nombres completos en `courses.yaml`. 3. Obsidian instalado. 4. Repo en `~/dev/video-course-ai-helper`, GitHub privado. 5. Sin Whisper ni ASR local.

## 10. Pendiente
- Plan de implementación (olas, DoD, código, commits): `docs/superpowers/plans/2026-10-09-video-course-ai-helper.md`.
- Ajustar `avisos_keywords` con el vocabulario de los profesores (lo hace Robert cuando quiera; hay default razonable).
- Decidir en F3 si las imágenes del vault van a git normal o a Git LFS (estimado ~300 MB para 60 clases).
