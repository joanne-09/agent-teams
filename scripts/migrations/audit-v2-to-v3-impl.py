#!/usr/bin/env python3
"""Idempotent audit schema migration v2 -> v3: add nullable actor_seat."""
import os, sys
from datetime import datetime, timezone
from urllib.parse import urlparse
url_str=os.environ['BSP_AUDIT_DB_URL']; scheme=urlparse(url_str).scheme
now=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
if scheme in ('sqlite','sqlite3'):
    import sqlite3
    path=url_str.replace(scheme+'://','',1)
    if not path.startswith('/'): path='/'+path.lstrip('/')
    conn=sqlite3.connect(path); cur=conn.cursor()
    version=int((cur.execute('SELECT version FROM audit_schema_meta WHERE id=1').fetchone() or [0])[0])
    if version < 3:
        columns=[row[1] for row in cur.execute('PRAGMA table_info(audit_log)').fetchall()]
        if 'actor_seat' not in columns: cur.execute('ALTER TABLE audit_log ADD COLUMN actor_seat TEXT NULL')
        cur.execute('INSERT OR REPLACE INTO audit_schema_meta (id,version,migrated_at) VALUES (1,3,?)',(now,)); conn.commit()
    conn.close(); print('audit-v2-to-v3: SQLite at v3')
elif scheme in ('postgresql','postgres'):
    import psycopg2
    conn=psycopg2.connect(url_str)
    with conn.cursor() as cur:
        cur.execute('ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS actor_seat TEXT NULL')
        cur.execute('INSERT INTO audit_schema_meta (id,version,migrated_at) VALUES (1,3,CURRENT_TIMESTAMP) ON CONFLICT (id) DO UPDATE SET version=3,migrated_at=CURRENT_TIMESTAMP')
    conn.commit(); conn.close(); print('audit-v2-to-v3: PostgreSQL at v3')
elif scheme in ('mysql','mysql+pymysql'):
    import pymysql
    u=urlparse(url_str.replace('mysql+pymysql://','mysql://'))
    conn=pymysql.connect(host=u.hostname or 'localhost',port=u.port or 3306,user=u.username,password=u.password,database=u.path.lstrip('/'))
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='audit_log' AND COLUMN_NAME='actor_seat'")
        if cur.fetchone()[0] == 0: cur.execute('ALTER TABLE audit_log ADD COLUMN actor_seat VARCHAR(16) NULL AFTER actor_role')
        cur.execute('INSERT INTO audit_schema_meta (id,version,migrated_at) VALUES (1,3,CURRENT_TIMESTAMP(3)) ON DUPLICATE KEY UPDATE version=3,migrated_at=CURRENT_TIMESTAMP(3)')
    conn.commit(); conn.close(); print('audit-v2-to-v3: MySQL at v3')
else:
    sys.stderr.write('audit-v2-to-v3: unsupported scheme: {}\n'.format(scheme)); sys.exit(2)
