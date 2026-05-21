#!/usr/bin/env bash
set -euo pipefail

# Environment knobs:
#   YOUTUBE_TRIAGE_PROVIDER=codex|gemini|claude|manual
#   YOUTUBE_TRIAGE_LIMIT=3
#   YOUTUBE_TRIAGE_TIMEOUT=300
#   YOUTUBE_TRIAGE_SETTLE_SECONDS=15
#   YOUTUBE_TRIAGE_DRY_RUN=1
#   YOUTUBE_TRIAGE_NO_BUILD=1

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
ROOT="$(cd -- "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd -P)"

PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

PROVIDER="${YOUTUBE_TRIAGE_PROVIDER:-codex}"
MODEL="${YOUTUBE_TRIAGE_MODEL:-}"
LIMIT="${YOUTUBE_TRIAGE_LIMIT:-3}"
TIMEOUT="${YOUTUBE_TRIAGE_TIMEOUT:-300}"
MAX_BODY_CHARS="${YOUTUBE_TRIAGE_MAX_BODY_CHARS:-}"
SETTLE_SECONDS="${YOUTUBE_TRIAGE_SETTLE_SECONDS:-15}"
DRY_RUN="${YOUTUBE_TRIAGE_DRY_RUN:-0}"
NO_BUILD="${YOUTUBE_TRIAGE_NO_BUILD:-0}"
RUNTIME_DIR="${YOUTUBE_TRIAGE_RUNTIME_DIR:-$ROOT/.wiki-runtime/youtube-triage}"
LOG_FILE="${YOUTUBE_TRIAGE_LOG_FILE:-$RUNTIME_DIR/run.log}"
LOCK_DIR="$RUNTIME_DIR/lock"

timestamp() {
  date "+%Y-%m-%dT%H:%M:%S%z"
}

log() {
  mkdir -p "$RUNTIME_DIR"
  mkdir -p "$(dirname -- "$LOG_FILE")"
  printf '[%s] %s\n' "$(timestamp)" "$*" | tee -a "$LOG_FILE"
}

release_lock() {
  rm -rf "$LOCK_DIR"
}

acquire_lock() {
  mkdir -p "$RUNTIME_DIR"
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    printf '%s\n' "$$" >"$LOCK_DIR/pid"
    trap release_lock EXIT INT TERM
    return 0
  fi

  local existing_pid=""
  if [[ -f "$LOCK_DIR/pid" ]]; then
    existing_pid="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
  fi

  if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" 2>/dev/null; then
    log "another youtube triage run is already active with pid $existing_pid"
    exit 0
  fi

  log "removing stale youtube triage lock"
  rm -rf "$LOCK_DIR"
  mkdir "$LOCK_DIR"
  printf '%s\n' "$$" >"$LOCK_DIR/pid"
  trap release_lock EXIT INT TERM
}

provider_command() {
  case "$PROVIDER" in
    codex|gemini|claude)
      printf '%s\n' "$PROVIDER"
      ;;
    manual)
      printf '%s\n' "true"
      ;;
    *)
      log "unsupported YOUTUBE_TRIAGE_PROVIDER: $PROVIDER"
      exit 2
      ;;
  esac
}

cd "$ROOT"
acquire_lock

if ! command -v python3 >/dev/null 2>&1; then
  log "python3 is not available on PATH"
  exit 127
fi

pending_output="$(python3 scripts/wiki_tool.py youtube-pending)"
if [[ "$pending_output" == "no pending YouTube sources" ]]; then
  log "no pending YouTube sources"
  exit 0
fi

provider_bin="$(provider_command)"
if ! command -v "$provider_bin" >/dev/null 2>&1; then
  log "$provider_bin is not available on PATH"
  exit 127
fi

if [[ "$SETTLE_SECONDS" =~ ^[0-9]+$ ]] && (( SETTLE_SECONDS > 0 )); then
  log "pending YouTube sources found; waiting ${SETTLE_SECONDS}s for file writes to settle"
  sleep "$SETTLE_SECONDS"
else
  log "pending YouTube sources found"
fi

while IFS= read -r pending_path; do
  [[ -n "$pending_path" ]] && log "queued: $pending_path"
done <<<"$pending_output"

cmd=(python3 scripts/wiki_tool.py youtube-triage --pending --provider "$PROVIDER" --limit "$LIMIT" --timeout "$TIMEOUT")

if [[ -n "$MODEL" ]]; then
  cmd+=(--model "$MODEL")
fi

if [[ -n "$MAX_BODY_CHARS" ]]; then
  cmd+=(--max-body-chars "$MAX_BODY_CHARS")
fi

if [[ "$DRY_RUN" == "1" || "$DRY_RUN" == "true" ]]; then
  cmd+=(--dry-run)
fi

if [[ "$NO_BUILD" == "1" || "$NO_BUILD" == "true" ]]; then
  cmd+=(--no-build)
fi

if (( $# > 0 )); then
  cmd+=("$@")
fi

log "running: ${cmd[*]}"
if "${cmd[@]}" >>"$LOG_FILE" 2>&1; then
  log "youtube triage completed"
else
  status=$?
  log "youtube triage failed with exit code $status"
  exit "$status"
fi
