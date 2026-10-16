#!/usr/bin/env bash
# Unattended run: detect new/incomplete classes in every course and process them with Claude Code (headless).
# No pending classes -> refresh the registry, copy root notes to Drive and exit 0 without spending tokens.
# Env: VCH_BUDGET_USD (default 30), VCH_MAX_TURNS (default 250), CLAUDE_BIN (default: claude on PATH).
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 1
# launchd / cron start with a minimal PATH: make uv and claude reachable
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

LOG_DIR="work/_logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/procesar-$(date +%F_%H%M).log"
LOCK="$LOG_DIR/.lock"

log() { printf '%s %s\n' "$(date '+%F %T')" "$*" >>"$LOG"; }

if ! mkdir "$LOCK" 2>/dev/null; then
  log "otra corrida en curso ($LOCK existe); salgo"
  exit 75
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

log "inicio (repo $REPO)"
uv run python -m pipeline pending --json >>"$LOG" 2>&1
rc=$?
case $rc in
  0)
    log "nada nuevo"
    uv run python -m pipeline registry >>"$LOG" 2>&1
    uv run python -m pipeline sync-root >>"$LOG" 2>&1
    log "fin (sin tokens)"
    exit 0
    ;;
  3)
    log "hay clases pendientes -> claude -p /procesar-nuevas (techo USD ${VCH_BUDGET_USD:-30}, ${VCH_MAX_TURNS:-250} turnos)"
    ;;
  *)
    log "pending terminó con código $rc (4 = solo errores de red/credenciales); no se lanza claude"
    exit "$rc"
    ;;
esac

"${CLAUDE_BIN:-claude}" -p "/procesar-nuevas" \
  --model opus \
  --max-turns "${VCH_MAX_TURNS:-250}" \
  --max-budget-usd "${VCH_BUDGET_USD:-30}" \
  --allowedTools "Read,Write,Edit,Grep,Glob,Agent,Skill,Bash(uv run python -m pipeline:*),Bash(ls:*),Bash(jq:*),Bash(git status:*)" \
  --disallowedTools "WebFetch,WebSearch,Bash(curl:*),Bash(wget:*),Bash(python3:*),Bash(git push:*)" \
  --output-format json >>"$LOG" 2>&1
rc=$?
log "claude terminó con código $rc"
exit "$rc"
