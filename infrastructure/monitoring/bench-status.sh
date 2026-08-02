#!/usr/bin/env bash
# Plan-phase status for the bench cockpit's top-right pane.
#
# WHY THIS REPLACED THE RAW DRIVER-LOG TAIL: between phases the driver is stopped, so that
# pane showed nothing but "no pending units — all phases drained" every 30 seconds. This shows
# where the plan of record actually is, and falls back to the driver log the moment a queue is
# running again — so the pane is useful in both states instead of one.
#
# Usage: watch -n 20 bash infrastructure/monitoring/bench-status.sh
set -u
M="$HOME/Shared/Computing Projects/MLECU"
DB="$M/ml/eval/bench/bench.sqlite"
STATUS="$M/ml/eval/bench/PHASE-STATUS.md"

echo "== PLAN: docs/PLAN-bench-integrity-e4-2026-08-01.md =="
[ -f "$STATUS" ] && sed -n '1,18p' "$STATUS"

echo
echo "== ledger =="
RUNNING=$(sqlite3 "$DB" "SELECT COUNT(*) FROM unit WHERE state='running';" 2>/dev/null)
PENDING=$(sqlite3 "$DB" "SELECT COUNT(*) FROM unit WHERE state='pending';" 2>/dev/null)
# is-active exits non-zero when inactive, so `|| echo` would append a second word
SVC=$(systemctl --user is-active mlecu-bench 2>/dev/null || true)
echo "pending=${PENDING:-?}  running=${RUNNING:-?}   service: ${SVC:-unknown}"

if [ "${RUNNING:-0}" != "0" ] || [ "${PENDING:-0}" != "0" ]; then
  echo
  echo "== driver log (queue active) =="
  tail -n 12 "$M/ml/finetuning/logs/bench-driver.log" 2>/dev/null
fi

echo
echo "== git =="
git -C "$M" log --oneline -4 2>/dev/null
