#!/usr/bin/env bash
# Plan-phase status for the bench cockpit's top-right pane.
#
# WHY THIS REPLACED THE RAW DRIVER-LOG TAIL: between phases the driver is stopped, so that pane
# showed nothing but "no pending units — all phases drained" every 30 seconds. This shows where
# the plan of record actually is, plus the corrected matrix filling in live, and falls back to
# the driver log whenever a queue is running.
#
# BUDGET: the pane is ~68 cols x 25 rows. Everything here is trimmed to fit — anything longer
# wraps and eats two rows. Full detail lives in ml/eval/bench/PHASE-STATUS.md.
#
# Usage: watch -n 20 bash infrastructure/monitoring/bench-status.sh
set -u
M="$HOME/Shared/Computing Projects/MLECU"
DB="$M/ml/eval/bench/bench.sqlite"
STATUS="$M/ml/eval/bench/PHASE-STATUS.md"

# checklist only (stop at the first blank line — headline/needs-Syed stay in the file)
[ -f "$STATUS" ] && awk 'NF==0{exit} {print}' "$STATUS"

echo
"$M/car/.venv/bin/python" "$M/infrastructure/monitoring/e2v2-scores.py" 2>/dev/null \
  || echo "  (scorer unavailable)"

DONE=$(sqlite3 "$DB" "SELECT COUNT(*) FROM unit WHERE phase='e2v2' AND state='done';" 2>/dev/null)
LEFT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM unit WHERE phase='e2v2' AND state='pending';" 2>/dev/null)
RUN=$(sqlite3 "$DB" "SELECT label||' '||ROUND((julianday('now')-julianday(started_at))*1440,0)||'m' FROM unit WHERE phase='e2v2' AND state='running';" 2>/dev/null)
FAIL=$(sqlite3 "$DB" "SELECT COUNT(*) FROM unit WHERE phase='e2v2' AND state='failed';" 2>/dev/null)
AVG=$(sqlite3 "$DB" "SELECT ROUND(AVG((julianday(ended_at)-julianday(started_at))*1440),0) FROM unit WHERE phase='e2v2' AND state='done';" 2>/dev/null)
SVC=$(systemctl --user is-active mlecu-bench 2>/dev/null || true)

echo
echo "done=${DONE:-?} left=${LEFT:-?} failed=${FAIL:-0} svc=${SVC:-?}$(
  [ -n "${AVG:-}" ] && [ "${LEFT:-0}" -gt 0 ] && echo "  ETA ~$(( LEFT * ${AVG%.*} / 60 ))h" )"
[ -n "${RUN:-}" ] && echo "RUNNING: ${RUN:0:64}"
[ "${FAIL:-0}" != "0" ] && echo "!! ${FAIL} FAILED — see driver log (pane below-right)"
echo "detail + open questions: ml/eval/bench/PHASE-STATUS.md"
