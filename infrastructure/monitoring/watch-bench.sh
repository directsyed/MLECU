#!/usr/bin/env bash
# MLECU benchmark cockpit — 4-pane tmux viewer for the multi-day pipeline.
# PURE VIEWER: closing it, or Ctrl-C in any pane, affects nothing. The driver is a systemd
# user service; only `systemctl --user stop mlecu-bench` actually stops work.
#   top-left     = ledger progress (per-phase counts + the unit running right now)
#   top-right    = driver log (unit starts, validations, duty trips, preemption)
#   bottom-left  = GPU vitals + lock assertions (3090 MUST read 810MHz / <200W)
#   bottom-right = llama-server log (model loads, print_timing throughput lines)
# Usage: bash infrastructure/monitoring/watch-bench.sh   (reattach: tmux attach -t bench)
set -u
M="$HOME/Shared/Computing Projects/MLECU"
DB="$M/ml/eval/bench/bench.sqlite"
S=bench

tmux kill-session -t "$S" 2>/dev/null
tmux new-session -d -s "$S"
tmux split-window -h -t "$S:0"
tmux split-window -v -t "$S:0.0"
tmux split-window -v -t "$S:0.2"

# pane 0 (top-left): ledger progress
tmux send-keys -t "$S:0.0" \
  "watch -n 20 'sqlite3 \"$DB\" \"SELECT phase||\\\" \\\"||state||\\\": \\\"||COUNT(*) FROM unit GROUP BY phase,state;\"; echo; echo RUNNING:; sqlite3 \"$DB\" \"SELECT label||\\\"  \\\"||ROUND((julianday(\\\"now\\\")-julianday(started_at))*1440,1)||\\\" min\\\" FROM unit WHERE state=\\\"running\\\";\"; echo; echo LAST-DONE:; sqlite3 \"$DB\" \"SELECT label||\\\"  \\\"||COALESCE(substr(note,1,28),\\\"\\\") FROM unit WHERE state IN (\\\"done\\\",\\\"failed\\\") ORDER BY ended_at DESC LIMIT 5;\"'" C-m

# pane 1 (bottom-left): GPU vitals + the lock assertion that protects the convicted card
tmux send-keys -t "$S:0.1" \
  "watch -n 5 'nvidia-smi --query-gpu=index,name,clocks.gr,power.draw,temperature.gpu,memory.used,utilization.gpu --format=csv,noheader; echo; echo \"3090 must be 810MHz and under 200W (watchdog ceiling)\"; echo; free -g | head -2; echo; for f in /sys/devices/system/edac/mc/mc*/ce_count; do printf \"%s=%s \" \$(basename \$(dirname \$f)) \$(cat \$f); done; echo \" <- ECC correctable (want all 0)\"'" C-m

# pane 2 (top-right): driver log
tmux send-keys -t "$S:0.2" \
  "tail -n 30 -f '$M/ml/finetuning/logs/bench-driver.log'" C-m

# pane 3 (bottom-right): server log, filtered to loads + throughput
tmux send-keys -t "$S:0.3" \
  "tail -n 200 -f '$M/ml/finetuning/logs/bench-server.log' | grep --line-buffered -iE 'print_timing|tokens per second|eval time|load|error|CUDA|====='" C-m

tmux select-pane -t "$S:0.0"
tmux attach -t "$S"
