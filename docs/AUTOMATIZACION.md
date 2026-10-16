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
- Herramientas permitidas al headless: Read/Write/Edit/Grep/Glob/Agent/Skill y Bash solo para `uv run python -m pipeline`, `ls`, `jq` y `git status`. Bloqueadas explícitamente: WebFetch/WebSearch, `curl`, `wget`, `python3` y `git push` (los transcripts son contenido externo: se minimiza lo que un texto inyectado podría ejecutar). Nada de git add/commit.
- Logs: `work/_logs/procesar-AAAA-MM-DD_HHMM.log` (salida JSON de claude incluida, con `total_cost_usd`). Lock en `work/_logs/.lock` evita dos corridas a la vez (si quedó colgado tras un crash: `rmdir work/_logs/.lock`).

## Programación activa: tarea programada de la app de Claude
- Tarea `vch-procesar-nuevas` (sección "Scheduled" de la app de Claude): **lunes a viernes 23:30** (cron `30 23 * * 1-5`; la app agrega unos minutos de demora). Corre mientras la app está abierta; si estaba cerrada, corre al abrirla.
- Hace lo mismo que el script: `pending` primero (sin pendientes responde "Sin clases nuevas" y no despacha agentes); con pendientes ejecuta `/procesar-nuevas`.
- Primera vez: en la app, abrir la tarea y tocar **"Run now"** (o fijarle un modo de permisos) para aprobar las herramientas; las aprobaciones quedan guardadas para las corridas siguientes.
- Por qué no LaunchAgent/cron: macOS (TCC) no deja que procesos lanzados por launchd escriban en `~/Library/CloudStorage` (Google Drive) sin dar "Acceso total al disco" a `/bin/bash`; la corrida quedaba colgada en `sync-root`. La app de Claude ya tiene ese acceso. `scripts/procesar-nuevas.sh` sigue sirviendo para correr a mano desde una terminal.

## Si algo queda bloqueado
`pending` muestra la etapa y el error exacto. Reintento: `uv run python -m pipeline <etapa> --course <c> --class <id> --force` (ej. `fetch` si Vimeo todavía no generó el VTT; volver a probar al día siguiente). Sin VTT `es-x-autogen` no se transcribe localmente: queda bloqueada hasta que Vimeo lo publique.

## Recordatorios
- Credenciales (`<CURSO>_VIMEO_URL/_PASSWORD`, `DRIVE_ROOT`) solo en `.env` (gitignored).
- La URL firmada del player expira ~24 h: `fetch` lista y baja en la misma corrida; no guardar URLs para después.
- Sin clases nuevas el script no llama a Claude: se puede programar diario sin costo.
