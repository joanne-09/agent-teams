#!/usr/bin/env bash
# Semantic Kanban Protocol handoff_card action for GitHub Project v2.
# Exit codes: 0 success; 2 usage; 3 missing dependency; 10 illegal handoff;
# 11 from-seat mismatch; 20 handoff cap reached; 21 projection lookup failed;
# 22 Role write failed; 23 comment failed; 24 audit write failed.
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
AUDIT_WRITER="${BSP_AUDIT_WRITER:-${SCRIPT_DIR}/audit-log-write.sh}"
# shellcheck source=lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"

usage() {
    printf 'Usage: %s --card <N> --from-seat <seat> --to-seat <seat> --reason <text> --project <OWNER/NUMBER> [--repo <OWNER/REPO>] [--needs <text>] [--artifacts <text>] [--handoff-cap <N>]\n' "${0##*/}" >&2
    exit 2
}

card="" from_seat="" to_seat="" reason="" project_ref="" repo_ref=""
needs="Read the card body and latest handoff before acting." artifacts="See the card and linked PRs." cap="${BOARD_SP_HANDOFF_CAP:-6}"
while [ "$#" -gt 0 ]; do
    case "$1" in
        --card) card="${2:-}"; shift 2 ;;
        --from-seat) from_seat="${2:-}"; shift 2 ;;
        --to-seat) to_seat="${2:-}"; shift 2 ;;
        --reason) reason="${2:-}"; shift 2 ;;
        --project) project_ref="${2:-}"; shift 2 ;;
        --repo) repo_ref="${2:-}"; shift 2 ;;
        --needs) needs="${2:-}"; shift 2 ;;
        --artifacts) artifacts="${2:-}"; shift 2 ;;
        --handoff-cap) cap="${2:-}"; shift 2 ;;
        -h|--help) usage ;;
        *) usage ;;
    esac
done
[ -n "${card}" ] && [ -n "${from_seat}" ] && [ -n "${to_seat}" ] && [ -n "${reason}" ] && [ -n "${project_ref}" ] || usage
case "${card}" in *[!0-9]*|''|0) usage ;; esac
case "${cap}" in *[!0-9]*|''|0) usage ;; esac
case "${from_seat}" in analyst|architect|rd|qa|em|human) ;; *) usage ;; esac
case "${to_seat}" in analyst|architect|rd|qa|em|human) ;; *) usage ;; esac
case "${project_ref}" in */*) ;; *) usage ;; esac
owner="${project_ref%/*}"; project_number="${project_ref#*/}"
[ -n "${owner}" ] || usage
case "${project_number}" in *[!0-9]*|''|0) usage ;; esac

# Authority is checked before any mutation. This mirrors board-canon.
legal=1
case "${from_seat}:${to_seat}" in
    analyst:architect|analyst:em|analyst:human) ;;
    architect:analyst|architect:rd|architect:qa|architect:em|architect:human) ;;
    rd:architect|rd:qa|rd:em) ;;
    qa:architect|qa:rd|qa:em|qa:human) ;;
    em:analyst|em:architect|em:rd|em:qa|em:human) ;;
    human:analyst|human:architect|human:rd|human:qa|human:em) ;;
    *) legal=0 ;;
esac
if [ "${legal}" -ne 1 ]; then
    "${AUDIT_WRITER}" --action-id 305 --decision A --skill operating-kanban \
        --payload "{\"card\":${card},\"from_seat\":\"${from_seat}\",\"to_seat\":\"${to_seat}\",\"reason\":\"illegal_handoff\"}" \
        --outcome failure --approval-stage auto --actor-seat "${from_seat}" || true
    printf 'illegal handoff: %s -> %s\n' "${from_seat}" "${to_seat}" >&2
    exit 10
fi

command -v gh >/dev/null 2>&1 || { printf 'missing dependency: gh\n' >&2; exit 3; }
command -v python3 >/dev/null 2>&1 || { printf 'missing dependency: python3\n' >&2; exit 3; }
if [ -z "${repo_ref}" ]; then repo_ref="$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || true)"; fi
[ -n "${repo_ref}" ] || { printf 'unable to resolve repository; pass --repo OWNER/REPO\n' >&2; exit 21; }

fields_json="$(gh project field-list "${project_number}" --owner "${owner}" --format json --limit 100)" || exit 21
items_json="$(gh project item-list "${project_number}" --owner "${owner}" --format json --limit 500)" || exit 21
comments_json="$(gh issue view "${card}" --repo "${repo_ref}" --json comments)" || exit 21

lookup="$(BSP_FIELDS_JSON="${fields_json}" BSP_ITEMS_JSON="${items_json}" BSP_COMMENTS_JSON="${comments_json}" BSP_CARD="${card}" BSP_TO_SEAT="${to_seat}" python3 - <<'PY'
import json, os, sys
fields_raw=json.loads(os.environ['BSP_FIELDS_JSON']); items_raw=json.loads(os.environ['BSP_ITEMS_JSON'])
fields=fields_raw if isinstance(fields_raw,list) else fields_raw.get('fields',[]) if isinstance(fields_raw,dict) else []
items=items_raw if isinstance(items_raw,list) else items_raw.get('items',[]) if isinstance(items_raw,dict) else []
role=next((f for f in fields if isinstance(f,dict) and f.get('name')=='Role'),None)
if not role: sys.exit(2)
options=role.get('options',[]) if isinstance(role.get('options',[]),list) else []
option=next((o for o in options if isinstance(o,dict) and o.get('name')==os.environ['BSP_TO_SEAT']),None)
if not option: sys.exit(3)
card=int(os.environ['BSP_CARD'])
item=next((i for i in items if isinstance(i,dict) and isinstance(i.get('content'),dict) and i['content'].get('number')==card),None)
if not item: sys.exit(4)
comments_raw=json.loads(os.environ['BSP_COMMENTS_JSON'])
comments=comments_raw.get('comments',[]) if isinstance(comments_raw,dict) else []
count=sum(1 for c in comments if '<!-- board-superpowers:handoff -->' in (c.get('body') or ''))
current=item.get('role')
if isinstance(current,dict): current=current.get('name')
project_id=''
if isinstance(items_raw,dict):
    project=items_raw.get('project',{})
    project_id=items_raw.get('id','') or (project.get('id','') if isinstance(project,dict) else '')
print('\t'.join([str(project_id),str(item.get('id','')),str(role.get('id','')),str(option.get('id','')),str(current or ''),str(count)]))
PY
)" || { printf 'Role field, option, or card item not found\n' >&2; exit 21; }
IFS="$(printf '\t')" read -r project_id item_id field_id option_id current_role handoff_count <<EOF
${lookup}
EOF
# project view is the authoritative source when item-list does not carry id.
if [ -z "${project_id}" ]; then project_id="$(gh project view "${project_number}" --owner "${owner}" --format json --jq .id)" || exit 21; fi
if [ -n "${current_role}" ] && [ "${current_role}" != "${from_seat}" ]; then
    printf 'from-seat mismatch: board has %s, caller supplied %s\n' "${current_role}" "${from_seat}" >&2
    exit 11
fi
if [ "${handoff_count}" -ge "${cap}" ]; then
    "${AUDIT_WRITER}" --action-id 305 --decision A --skill operating-kanban \
        --payload "{\"card\":${card},\"from_seat\":\"${from_seat}\",\"to_seat\":\"${to_seat}\",\"reason\":\"handoff_cap\"}" \
        --outcome failure --approval-stage auto --actor-seat "${from_seat}" || true
    printf 'handoff cap reached: %s >= %s\n' "${handoff_count}" "${cap}" >&2
    exit 20
fi

gh project item-edit --id "${item_id}" --project-id "${project_id}" --field-id "${field_id}" --single-select-option-id "${option_id}" >/dev/null || exit 22
comment="<!-- board-superpowers:handoff -->
**Handoff**: \`${from_seat}\` -> \`${to_seat}\`
**Reason**: ${reason}
**Needs from you**: ${needs}
**Artifacts**: ${artifacts}"
gh issue comment "${card}" --repo "${repo_ref}" --body "${comment}" >/dev/null || exit 23
audit_payload="$(BSP_CARD="${card}" BSP_FROM_SEAT="${from_seat}" BSP_TO_SEAT="${to_seat}" BSP_REASON="${reason}" BSP_HANDOFF_COUNT="$((handoff_count + 1))" python3 -c 'import json,os; print(json.dumps({"card":int(os.environ["BSP_CARD"]),"from_seat":os.environ["BSP_FROM_SEAT"],"to_seat":os.environ["BSP_TO_SEAT"],"reason":os.environ["BSP_REASON"],"handoff_count":int(os.environ["BSP_HANDOFF_COUNT"])}))')"
"${AUDIT_WRITER}" --action-id 300 --decision A --skill operating-kanban \
    --payload "${audit_payload}" \
    --outcome success --approval-stage auto --actor-role producer --actor-seat "${from_seat}" || exit 24
BSP_CARD="${card}" BSP_FROM_SEAT="${from_seat}" BSP_TO_SEAT="${to_seat}" BSP_HANDOFF_COUNT="$((handoff_count + 1))" python3 -c 'import json,os; print(json.dumps({"card":int(os.environ["BSP_CARD"]),"from_seat":os.environ["BSP_FROM_SEAT"],"to_seat":os.environ["BSP_TO_SEAT"],"handoff_count":int(os.environ["BSP_HANDOFF_COUNT"])}))'
