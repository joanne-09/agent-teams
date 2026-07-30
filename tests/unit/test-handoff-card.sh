#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
TMP_ROOT="$(mktemp -d)"
trap 'rm -rf "${TMP_ROOT}"' EXIT
mkdir -p "${TMP_ROOT}/bin"
export FAKE_LOG="${TMP_ROOT}/gh.log"
export FAKE_AUDIT="${TMP_ROOT}/audit.json"
export PATH="${TMP_ROOT}/bin:${PATH}"

cat > "${TMP_ROOT}/bin/gh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "${FAKE_LOG}"
case "$1 $2" in
  "project field-list")
    printf '%s\n' '{"fields":[{"id":"ROLE_FIELD","name":"Role","options":[{"id":"OPT_ARCH","name":"architect"},{"id":"OPT_RD","name":"rd"},{"id":"OPT_QA","name":"qa"}]}]}' ;;
  "project item-list")
    role="${FAKE_ROLE:-architect}"
    printf '{"id":"PROJECT_ID","items":[{"id":"ITEM_ID","role":"%s","content":{"number":42}}]}\n' "${role}" ;;
  "issue view")
    if [ "${FAKE_CAP:-0}" = 1 ]; then
      printf '%s\n' '{"comments":[{"body":"<!-- board-superpowers:handoff -->"},{"body":"<!-- board-superpowers:handoff -->"},{"body":"<!-- board-superpowers:handoff -->"},{"body":"<!-- board-superpowers:handoff -->"},{"body":"<!-- board-superpowers:handoff -->"},{"body":"<!-- board-superpowers:handoff -->"}]}'
    else
      printf '%s\n' '{"comments":[]}'
    fi ;;
  "project item-edit"|"issue comment") : ;;
  "project view") printf '%s\n' '{"id":"PROJECT_ID"}' ;;
  "repo view") printf '%s\n' 'acme/repo' ;;
  *) echo "unexpected gh call: $*" >&2; exit 99 ;;
esac
SH
chmod +x "${TMP_ROOT}/bin/gh"

cat > "${TMP_ROOT}/audit-writer" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
payload=''
while [ "$#" -gt 0 ]; do
  case "$1" in --payload) payload="$2"; shift 2 ;; *) shift ;; esac
done
printf '%s\n' "${payload}" > "${FAKE_AUDIT}"
SH
chmod +x "${TMP_ROOT}/audit-writer"
export BSP_AUDIT_WRITER="${TMP_ROOT}/audit-writer"
SCRIPT="${ROOT}/scripts/handoff-card.sh"

# Illegal edge is rejected before any gh read/mutation.
: > "${FAKE_LOG}"
rc=0
bash "${SCRIPT}" --card 42 --from-seat analyst --to-seat rd --reason skip --project acme/7 --repo acme/repo >/dev/null 2>&1 || rc=$?
[ "${rc}" = 10 ] || { echo "FAIL: illegal edge rc=${rc}" >&2; exit 1; }
[ ! -s "${FAKE_LOG}" ] || { echo "FAIL: gh called before authority refusal" >&2; exit 1; }

# Successful handoff mutates Role, comments, and emits valid escaped JSON.
: > "${FAKE_LOG}"
unset FAKE_CAP FAKE_ROLE
bash "${SCRIPT}" --card 42 --from-seat architect --to-seat rd --reason 'needs "quoted" context' --project acme/7 --repo acme/repo >/dev/null
python3 -c 'import json,os; row=json.load(open(os.environ["FAKE_AUDIT"])); assert row["reason"] == "needs \"quoted\" context"; assert row["handoff_count"] == 1'
grep -q '^project item-edit ' "${FAKE_LOG}" || { echo "FAIL: Role mutation missing" >&2; exit 1; }
grep -q '^issue comment ' "${FAKE_LOG}" || { echo "FAIL: structured comment missing" >&2; exit 1; }

# Cap and from-seat mismatch refuse before mutation.
: > "${FAKE_LOG}"; export FAKE_CAP=1
rc=0
bash "${SCRIPT}" --card 42 --from-seat architect --to-seat rd --reason cap --project acme/7 --repo acme/repo >/dev/null 2>&1 || rc=$?
[ "${rc}" = 20 ] || { echo "FAIL: cap rc=${rc}" >&2; exit 1; }
! grep -q '^project item-edit ' "${FAKE_LOG}" || { echo "FAIL: mutation occurred at cap" >&2; exit 1; }

: > "${FAKE_LOG}"; unset FAKE_CAP; export FAKE_ROLE=qa
rc=0
bash "${SCRIPT}" --card 42 --from-seat architect --to-seat rd --reason mismatch --project acme/7 --repo acme/repo >/dev/null 2>&1 || rc=$?
[ "${rc}" = 11 ] || { echo "FAIL: mismatch rc=${rc}" >&2; exit 1; }
! grep -q '^project item-edit ' "${FAKE_LOG}" || { echo "FAIL: mutation occurred on mismatch" >&2; exit 1; }

echo PASS
