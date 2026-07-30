#!/usr/bin/env bash
# List cards from a GitHub Project as JSON, including the orthogonal Role lane.
# Args: --owner <login> --project <number> [--status <name>] [--role <seat>]
# Stdout item: number, title, status, role (seat or null), url, item_id.
# Exit: 0 success (including empty); 1 invalid args, gh failure, or parse error.
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
# shellcheck source=scripts/lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"
OWNER="" PROJECT="" STATUS="" ROLE=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --owner) OWNER="${2:-}"; shift 2 ;;
        --project) PROJECT="${2:-}"; shift 2 ;;
        --status) STATUS="${2:-}"; shift 2 ;;
        --role) ROLE="${2:-}"; shift 2 ;;
        *) bsp_die "unknown arg: $1" ;;
    esac
done
[ -n "${OWNER}" ] || bsp_die "missing --owner"
[ -n "${PROJECT}" ] || bsp_die "missing --project"
if [ -n "${ROLE}" ]; then case "${ROLE}" in analyst|architect|rd|qa|em|human) ;; *) bsp_die "invalid --role: ${ROLE}" ;; esac; fi
bsp_require_cmd gh
bsp_require_cmd python3

BSP_STATUS_FILTER="${STATUS}" BSP_ROLE_FILTER="${ROLE}" \
gh project item-list "${PROJECT}" --owner "${OWNER}" --format json --limit 500 \
| BSP_STATUS_FILTER="${STATUS}" BSP_ROLE_FILTER="${ROLE}" python3 -c '
import json, os, sys
items=json.load(sys.stdin).get("items",[])
status_filter=os.environ.get("BSP_STATUS_FILTER","")
role_filter=os.environ.get("BSP_ROLE_FILTER","")
out=[]
for item in items:
    content=item.get("content") or {}
    if content.get("type") != "Issue": continue
    status=item.get("status") or ""
    role=item.get("role")
    if isinstance(role,dict): role=role.get("name")
    role=role or None
    if status_filter and status != status_filter: continue
    if role_filter and role != role_filter: continue
    out.append({"number":content.get("number"),"title":content.get("title"),"status":status,"role":role,"url":content.get("url"),"item_id":item.get("id")})
print(json.dumps(out,ensure_ascii=False,indent=2))
'
