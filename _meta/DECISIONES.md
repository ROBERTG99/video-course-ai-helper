# DECISIONES — Video Course AI Helper

## 2026-10-09 · Diseño inicial (ver spec para opciones descartadas)
- **Repo activo en `~/dev/video-course-ai-helper`** (GitHub privado `ROBERTG99/video-course-ai-helper`; nombre con guiones porque GitHub y las rutas no aceptan espacios; título visible "Video Course AI Helper"), Drive solo destino final + backup crudo. Por qué: patrón BD2 + playbook §1.7 (Drive causa errores de edición y git).
- **Transcript = VTT de Vimeo vía yt-dlp (`text_tracks` del player config)**. **Sin Whisper ni ASR local** (decisión de Robert): una clase sin track se reporta como BLOQUEADO. Por qué: Vimeo ya genera `es-x-autogen`; no vale mantener un segundo camino.
- **Frames = pipeline propio (ffmpeg + pHash + vision + OCR)**, no tools de terceros. Por qué: control del formato y alineación con timestamps; los tools existentes no integran con el estado por clase.
- **Análisis = subagentes en sesión para pilot/tandas; `claude -p` para la rutina semanal.** Por qué: desde 2026-06-15 `claude -p` consume crédito SDK separado; conviene gastar el interactivo en las tandas grandes y el SDK en 1 clase/semana.
- **Opus solo en `verificador-avisos` e integración de temas.** Por qué: playbook §3; el único lugar donde el recall vale el costo es en lo que el profesor dijo sobre exámenes/entregas.
- **Imágenes con link markdown relativo, notas con wikilink.** Por qué: las imágenes deben verse también en Drive/otros viewers; los wikilinks son lo que arma el grafo.
- **Plantilla de nota fija antes de cualquier fan-out** (§4.6 playbook). Cambios de plantilla = nueva decisión + re-corrida explícita.
- **Retrieval = `player_embed_url` firmada de la API del showcase + yt-dlp con Referer vimeo.com** (2026-10-09). Por qué: la URL del showcase falla con yt-dlp 2026.08 (API client `web` exige login); la ruta del player no. La firma expira ~24 h: listar y bajar en la misma corrida.
- **Resultados fuera de GitHub**: `vault/`, `raw/`, `work/`, `state/` gitignored; plantillas en `templates/`; Drive es el backup. Por qué: pedido de Robert; el repo es código + plan + prompts.
- **Espejo en Drive en `<Curso>/notas/`** (no `clases/`): incluye temas y MOC, no solo clases.
- **Commits por tarea del plan autorizados** (2026-10-09); fuera del plan sigue el "ok" previo.
- **Videos solo en `_clases-dump`** (no duplicados en la carpeta del curso); la nota lleva `video_path`. Por qué: ~40 GB, duplicarlos no aporta.
- **Track `en-x-autogen` se acepta cuando es el único** (2026-10-09): Vimeo etiqueta mal el idioma en 5 clases pero el texto es español; `pick_vtt` prefiere `es-x-autogen` y si no hay, toma el que exista. Sigue sin haber ASR local.
- **`validate` antes de `integrate` con slugs propios** (2026-10-09): el validador cuenta como existentes los slugs de `temas-candidatos.json` de la clase; evita falsos wikilinks rotos sin reordenar las etapas.
- **Agentes por clase leen su propio prompt de `work/`** (2026-10-09): `analysis-prompt.md`/`avisos-prompt.md` son únicos por clase (nadie más los lee), así que el orquestador le indica la ruta en vez de pegar 70K chars; respeta el espíritu de §4.4 (no N agentes sobre el mismo archivo) y ahorra contexto del orquestador.
- **Verificadores opus en paralelo dentro del tope de 4** (2026-10-09): el plan decía secuencial; se corren intercalados con analistas sin superar 4 agentes simultáneos.
- **`integrate` por tanda, no solo al cerrar el curso** (2026-10-09): así la tanda siguiente ve los temas existentes y reusa slugs.
- **Pilot sin revisión humana previa a las tandas** (2026-10-09): Robert pidió "arrancar y no frenar hasta terminar"; el checkpoint humano de T12 queda como revisión posterior. Cualquier ajuste se aplica con `--force` por clase.
- **Verificador opus con ≤3 clases por despacho** (2026-10-09): con 4 clases topó `maxTurns: 10` (los informes se escribieron igual).
- **Duplicados de temas: el integrador propone, el script fusiona** (`merge-temas a=b`), nunca el agente borra notas.

## 2026-10-09 · Reorganización del vault (pedido de Robert tras revisar las notas)
- **Vault orientado a unidades, no a temas atómicos**: por curso, un documento completo por unidad del MOC (`vault/<c>/unidades/NN-<slug>.md`, 6–9 por curso) que integra lo visto en todas las clases, con links a la sección exacta de cada nota de clase (`[[<class_id>#<H3>|Clase N]]`). Por qué: ~530 notas de 1 párrafo no sirven para estudiar; Robert pidió documentos completos "como el MOC".
- **Temas atómicos = insumo interno**: se mueven a `work/<c>/temas/` (no se borran; alimentan al redactor de unidades). El outline del curso pasa a `work/<c>/units.json` (derivado del `## Mapa` de cada MOC); los temas nuevos de cada clase se asignan a una unidad existente.
- **Notas de clase sin timestamps**: se quitan los `[hh:mm:ss]` de las 45 notas; el analista ya no los escribe y el validador no los exige. Siguen solo en artefactos internos (transcript, temas-candidatos, informes del verificador). El resto de la plantilla de clase NO cambia.
- **Links de las notas de clase**: `[[tema-slug]]` se reescriben a `[[NN-unidad#Sección|título]]` según el `map.json` que escribe el redactor de cada unidad.
- **MOC = índice**: unidades (con resumen de 1 línea) + clases + avisos + calendario; canvas = curso → unidades → secciones. `00-MOC-2026.md` y `calendario.md` también se espejan a Drive (`2026/`).
- **Todos los agentes en opus** (2026-10-09, pedido explícito de Robert): reemplaza el reparto sonnet/haiku del playbook para este proyecto.
- **Nombre de nota de clase = `<curso>-<class_id>.md`** (2026-10-15): había 7 class_id repetidos entre cursos (misma fecha y número) y Obsidian resuelve links por basename → 165 links ambiguos. El class_id interno (state/work/raw/img/dump) no cambia; solo el nombre de la nota y los links. Links con ruta no sirven porque el espejo en Drive usa otras carpetas.
