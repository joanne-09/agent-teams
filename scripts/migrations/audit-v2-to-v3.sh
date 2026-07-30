#!/usr/bin/env bash
# Lazy, idempotent audit schema migration v2 -> v3: add actor_seat.
set -euo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
# shellcheck source=scripts/lib/common.sh
. "${SCRIPT_DIR}/../lib/common.sh"
AUDIT_DB_URL="$(bsp_resolve_audit_db_url)"
[ -n "${AUDIT_DB_URL}" ] || exit 0
REPO_ROOT="$(bsp_primary_repo_root "${PWD}" 2>/dev/null || printf '%s' "${PWD}")"
VENV_PYTHON="$(bsp_ensure_venv "${REPO_ROOT}")" || bsp_die "venv unavailable for migration"
BSP_AUDIT_DB_URL="${AUDIT_DB_URL}" "${VENV_PYTHON}" "${SCRIPT_DIR}/audit-v2-to-v3-impl.py"
