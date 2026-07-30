#!/usr/bin/env bash
# Render a seat-bound board-superpowers kickoff prompt.
# Exit: 0 success; 2 usage; 3 invalid seat; 4 invalid format/card.
set -euo pipefail

usage() {
    printf 'Usage: %s --seat <analyst|architect|rd|qa|em|human> [--card <N>] [--format paste|subagent|cron]\n' "${0##*/}" >&2
    exit 2
}

seat="" card="" format="paste"
while [ "$#" -gt 0 ]; do
    case "$1" in
        --seat) seat="${2:-}"; shift 2 ;;
        --card) card="${2:-}"; shift 2 ;;
        --format) format="${2:-}"; shift 2 ;;
        -h|--help) usage ;;
        *) usage ;;
    esac
done
case "${seat}" in analyst|architect|rd|qa|em|human) ;; *) printf 'invalid seat: %s\n' "${seat}" >&2; exit 3 ;; esac
case "${format}" in paste|subagent|cron) ;; *) printf 'invalid format: %s\n' "${format}" >&2; exit 4 ;; esac
if [ -n "${card}" ]; then
    case "${card}" in *[!0-9]*|''|0) printf 'card must be a positive integer\n' >&2; exit 4 ;; esac
fi

token="[role:${seat}]"
[ -n "${card}" ] && token="${token} [board-card:#${card}]"
case "${seat}" in
    em) task="Run the team briefing, triage constraints, then dispatch the next legal role-owned work." ;;
    analyst) task="Intake and shape the requirement; finish by handing a Backlog card to architect." ;;
    architect) task="Author or decompose the specification; do not edit production code." ;;
    rd) task="Consume the assigned implementation card through the existing TDD delivery lifecycle." ;;
    qa) task="Verify the assigned delivery independently and record evidence; do not fix production code." ;;
    human) task="Review the merge gate or answer the explicit question recorded on the card." ;;
esac
prompt="${token} ${task} Read the board and its latest handoff comment before acting."
case "${format}" in
    paste) printf '%s\n' "${prompt}" ;;
    subagent) printf 'Prompt: %s\n' "${prompt}" ;;
    cron) printf "claude -p '%s'\n" "$(printf '%s' "${prompt}" | sed "s/'/'\\\\''/g")" ;;
esac
