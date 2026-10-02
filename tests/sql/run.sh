#!/usr/bin/env bash
# Run the community schema tests against a throwaway local Postgres:
#   tests/sql/run.sh
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"; root="$here/../.."
bin="$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -V | tail -1)"; [ -n "$bin" ] || bin="$(dirname "$(command -v postgres)")"
tmp="$(mktemp -d)"; port=$((54000 + RANDOM % 1000))
as_pg() { if [ "$(id -u)" = 0 ]; then su postgres -s /bin/bash -c "$*"; else bash -c "$*"; fi; }
chmod 777 "$tmp"
as_pg "'$bin/initdb' -D '$tmp/db' -A trust -U postgres >/dev/null"
as_pg "'$bin/pg_ctl' -D '$tmp/db' -o '-p $port -k $tmp -c listen_addresses=' -l '$tmp/log' -w start >/dev/null"
trap 'as_pg "\"$bin/pg_ctl\" -D \"$tmp/db\" -m immediate stop >/dev/null" || true; rm -rf "$tmp"' EXIT
psql=(psql -h "$tmp" -p "$port" -U postgres -v ON_ERROR_STOP=1 -q -X)
"${psql[@]}" -c "create database pp" >/dev/null
"${psql[@]}" -d pp -f "$here/supabase_stubs.sql" >/dev/null
for f in "$root"/supabase/migrations/*.sql; do "${psql[@]}" -d pp -f "$f" >/dev/null; done
"${psql[@]}" -d pp -f "$root/supabase/seed.sql" >/dev/null
for f in "$here"/*_test.sql; do "${psql[@]}" -d pp -f "$f" -t; done
