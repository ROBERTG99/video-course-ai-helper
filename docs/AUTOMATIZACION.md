# Automatización: qué hay que bajar y cómo procesarlo

## Qué detecta `pending`
`uv run python -m pipeline pending [--course X] [--offline] [--json]` lista, por curso, el showcase de Vimeo (misma API que `list-showcase`, con los `class_id` de `naming.assign_ids`) y lo cruza con `state/<curso>/*.json`:

| estado | significa |
|---|---|
| `nueva` | está publicada en Vimeo y no tiene state (nunca se bajó) |
| `incompleta:<etapa>` | primera etapa de las 7 (`fetch … sync`) que no está `ok` |
| `bloqueada:<etapa>: <error>` | una etapa quedó `blocked` (ej. `fetch: sin VTT en Vimeo`) |
| `error: <msg>` | no se pudo consultar ese curso (red, password, `.env`); los demás siguen |

Las clases con las 7 etapas `ok` no aparecen. Exit code: `0` nada pendiente, `3` hay pendientes, `4` solo errores. `--offline` mira solo `state/` (sin red ni `.env`).

## Registro
`uv run python -m pipeline registry [--offline]` escribe `vault/clases-registro.md`: pendientes + una tabla por curso (número, link a la nota, duración, estado, unidades que usan sus temas) y cómo procesar lo pendiente. Está linkeado desde `00-MOC-2026` y se copia a Drive como `2026/clases-registro.md` (`sync` o `sync-root`). `units-finish` y `sync` no tocan la red; si el registro no existe, `units-finish` lo crea offline.

## Tres modos
1. **Un curso, manual:** en Claude Code (este repo) `/nueva-clase <curso>`.
2. **Todos los cursos, manual:** `/procesar-nuevas` → corre `pending`, aplica `/nueva-clase` a cada curso con algo nuevo/incompleto (máx. 4 agentes, todos opus), reintenta una vez lo bloqueado, cierra con `registry` + `sync-root` y anota en `_meta/PROGRESS.md`.
3. **Desatendido:** `scripts/procesar-nuevas.sh`. Primero corre `pending` (barato): si no hay nada, solo refresca el registro y Drive y sale 0 **sin gastar tokens**. Si hay, lanza `claude -p "/procesar-nuevas" --model opus` con techo.

## Costos y techos
- `VCH_BUDGET_USD` (default `30`) → `--max-budget-usd`; `VCH_MAX_TURNS` (default `250`) → `--max-turns`. Ej.: `VCH_BUDGET_USD=15 scripts/procesar-nuevas.sh`.
- Herramientas permitidas al headless: Read/Write/Edit/Grep/Glob/Agent/Skill y Bash solo para `uv run`, `ls`, `jq`, `python3`, `cat`, `grep`, `git status` (nada de git add/commit).
- Logs: `work/_logs/procesar-AAAA-MM-DD_HHMM.log` (salida JSON de claude incluida, con `total_cost_usd`). Lock en `work/_logs/.lock` evita dos corridas a la vez (si quedó colgado tras un crash: `rmdir work/_logs/.lock`).

## Programarlo (ejemplo, NO instalado)
`~/Library/LaunchAgents/com.robert.vch.procesar.plist`, todos los días 23:30:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.robert.vch.procesar</string>
  <key>ProgramArguments</key><array>
    <string>/bin/bash</string><string>/Users/robert/dev/video-course-ai-helper/scripts/procesar-nuevas.sh</string>
  </array>
  <key>EnvironmentVariables</key><dict><key>VCH_BUDGET_USD</key><string>30</string></dict>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>23</integer><key>Minute</key><integer>30</integer></dict>
  <key>StandardOutPath</key><string>/Users/robert/dev/video-course-ai-helper/work/_logs/launchd.out</string>
  <key>StandardErrorPath</key><string>/Users/robert/dev/video-course-ai-helper/work/_logs/launchd.err</string>
</dict></plist>
```
Activar: `launchctl load ~/Library/LaunchAgents/com.robert.vch.procesar.plist` (desactivar con `unload`). Claude Code tiene que estar logueado en la Mac.

## Si algo queda bloqueado
`pending` muestra la etapa y el error exacto. Reintento: `uv run python -m pipeline <etapa> --course <c> --class <id> --force` (ej. `fetch` si Vimeo todavía no generó el VTT; volver a probar al día siguiente). Sin VTT `es-x-autogen` no se transcribe localmente: queda bloqueada hasta que Vimeo lo publique.

## Recordatorios
- Credenciales (`<CURSO>_VIMEO_URL/_PASSWORD`, `DRIVE_ROOT`) solo en `.env` (gitignored).
- La URL firmada del player expira ~24 h: `fetch` lista y baja en la misma corrida; no guardar URLs para después.
- Sin clases nuevas el script no llama a Claude: se puede programar diario sin costo.
