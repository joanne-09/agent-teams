#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
TMP_ROOT="$(mktemp -d)"
trap 'rm -rf "${TMP_ROOT}"' EXIT
export HOME="${TMP_ROOT}/home"
REPO="${TMP_ROOT}/repo"
mkdir -p "${HOME}/.board-superpowers" "${REPO}/.board-superpowers"
# shellcheck source=scripts/lib/common.sh
source "${ROOT}/scripts/lib/common.sh"
PYTHON_BIN="$(command -v python)"
bsp_ensure_venv() { printf '%s\n' "${PYTHON_BIN}"; }

assert_class() {
    expected="$1" action="$2" seat="${3:-}"
    actual="$(bsp_resolve_autonomy_class "${action}" "${REPO}" "${seat}" 2>/dev/null)"
    [ "${actual}" = "${expected}" ] || {
        printf 'FAIL: action=%s seat=%s expected=%s actual=%s\n' "${action}" "${seat}" "${expected}" "${actual}" >&2
        exit 1
    }
}

# Legacy default, seat specialization, unknown-seat fallback.
assert_class R 3
assert_class A 3 architect
assert_class N 3 rd
assert_class R 3 unknown-seat

# Hard floor: a project override cannot promote an illegal seat action.
cat > "${REPO}/.board-superpowers/config.local.yml" <<'YAML'
autonomy_overrides:
  - action_id: 3
    class: A
YAML
assert_class N 3 rd

# Precedence: project seat override wins a user generic override.
cat > "${HOME}/.board-superpowers/overrides.yml" <<'YAML'
autonomy_overrides:
  - action_id: 6
    class: A
YAML
cat > "${REPO}/.board-superpowers/config.local.yml" <<'YAML'
seat_overrides:
  architect:
    6: R
YAML
assert_class R 6 architect

# Within the project layer, a generic override wins a seat override.
cat > "${REPO}/.board-superpowers/config.local.yml" <<'YAML'
seat_overrides:
  architect:
    6: R
autonomy_overrides:
  - action_id: 6
    class: A
YAML
assert_class A 6 architect

echo PASS
