#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
SCRIPT="${ROOT}/scripts/dispatch-agent.sh"

out="$(bash "${SCRIPT}" --seat em --format paste)"
case "${out}" in "[role:em] "*) ;; *) echo "FAIL: EM role token missing" >&2; exit 1 ;; esac

out="$(bash "${SCRIPT}" --seat architect --card 42 --format subagent)"
case "${out}" in *"[role:architect] [board-card:#42]"*) ;; *) echo "FAIL: architect/card token missing" >&2; exit 1 ;; esac

out="$(bash "${SCRIPT}" --seat rd --card 7 --format cron)"
case "${out}" in "claude -p '"*"[role:rd] [board-card:#7]"*) ;; *) echo "FAIL: cron form malformed" >&2; exit 1 ;; esac

if bash "${SCRIPT}" --seat root >/dev/null 2>&1; then echo "FAIL: invalid seat accepted" >&2; exit 1; fi
if bash "${SCRIPT}" --seat rd --card 0 >/dev/null 2>&1; then echo "FAIL: zero card accepted" >&2; exit 1; fi

echo PASS
