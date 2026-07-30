#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
TMPDIR=$(mktemp -d)
trap 'rm -rf "${TMPDIR}"' EXIT

DB="${TMPDIR}/fresh.db"
sqlite3 "${DB}" < "${ROOT}/scripts/lib/audit-schema.sqlite.sql"

# Assert 1: audit_log has v2 event_uuid and v3 actor_seat columns
COLS=$(sqlite3 "${DB}" "PRAGMA table_info(audit_log)" | awk -F'|' '{print $2}' | sort)
echo "${COLS}" | grep -q '^event_uuid$' || { echo "FAIL: event_uuid column missing"; exit 1; }
echo "${COLS}" | grep -q '^actor_seat$' || { echo "FAIL: actor_seat column missing"; exit 1; }

# Assert 2: UNIQUE index on event_uuid exists
sqlite3 "${DB}" "SELECT name FROM sqlite_master WHERE type='index' AND name='audit_event_uuid_uniq'" \
    | grep -q audit_event_uuid_uniq || { echo "FAIL: UNIQUE index missing"; exit 1; }

# Assert 3: same event_uuid INSERT twice — second INSERT noop (with INSERT OR IGNORE) or fails (without)
sqlite3 "${DB}" "INSERT INTO audit_log (timestamp,project,session_id,actor_role,action_id,payload,outcome,approval_stage,event_uuid) VALUES ('2026-01-01','p/1','s1','consumer',200,'{}','success','auto','test-uuid-1')"
RC=0
sqlite3 "${DB}" "INSERT INTO audit_log (timestamp,project,session_id,actor_role,action_id,payload,outcome,approval_stage,event_uuid) VALUES ('2026-01-02','p/1','s2','consumer',201,'{}','success','auto','test-uuid-1')" 2>/dev/null || RC=$?
[ "${RC}" != 0 ] || { echo "FAIL: duplicate event_uuid INSERT should fail (UNIQUE constraint)"; exit 1; }

# Assert 4: audit_schema_meta version is 3 (fresh schema = v3)
VER=$(sqlite3 "${DB}" "SELECT version FROM audit_schema_meta WHERE id=1")
[ "${VER}" = 3 ] || { echo "FAIL: expected version 3, got ${VER}"; exit 1; }

# Assert 5: NULL event_uuid allowed (multiple NULLs OK in SQLite UNIQUE)
sqlite3 "${DB}" "INSERT INTO audit_log (timestamp,project,session_id,actor_role,action_id,payload,outcome,approval_stage) VALUES ('2026-01-03','p/1','s3','consumer',202,'{}','success','auto')"
sqlite3 "${DB}" "INSERT INTO audit_log (timestamp,project,session_id,actor_role,action_id,payload,outcome,approval_stage) VALUES ('2026-01-04','p/1','s4','consumer',203,'{}','success','auto')"
NULL_COUNT=$(sqlite3 "${DB}" "SELECT COUNT(*) FROM audit_log WHERE event_uuid IS NULL")
[ "${NULL_COUNT}" = 2 ] || { echo "FAIL: 2 NULL event_uuid rows should coexist, got ${NULL_COUNT}"; exit 1; }

# Assert 6: actor_seat is nullable and stores canonical seat attribution.
sqlite3 "${DB}" "INSERT INTO audit_log (timestamp,project,session_id,actor_role,actor_seat,action_id,payload,outcome,approval_stage) VALUES ('2026-01-05','p/1','s5','producer','architect',300,'{}','success','auto')"
[ "$(sqlite3 "${DB}" "SELECT actor_seat FROM audit_log WHERE action_id=300")" = architect ] || { echo "FAIL: actor_seat did not round-trip"; exit 1; }

echo "PASS"
