#!/usr/bin/env bash
# MLECU judge cockpit — 3-pane tmux viewer (pure viewer: closing it affects nothing).
#   top    = live tokens/sec from llama-judge (journal print_timing lines)
#   middle = judge verdict feed (one line per doc)
#   bottom = GPU vitals + service health + flight-recorder heartbeat (line count must grow)
# Usage: bash infrastructure/monitoring/watch-judge.sh   (reattach: tmux attach -t watch)
set -u
MLECU="$HOME/Shared/Computing Projects/MLECU"
TIER_LOG="$MLECU/ml/curation/data/ref-tier-run.log"
S=watch

tmux kill-session -t "$S" 2>/dev/null
tmux new-session -d -s "$S"
tmux split-window -v -t "$S:0"
tmux split-window -v -t "$S:0"
tmux select-layout -t "$S:0" even-vertical

tmux send-keys -t "$S:0.0" \
  "journalctl -u llama-judge -f -o cat | grep --line-buffered 'print_timing'" C-m
tmux send-keys -t "$S:0.1" \
  "tail -n 20 -f '$TIER_LOG'" C-m
tmux send-keys -t "$S:0.2" \
  "watch -n 5 'nvidia-smi --query-gpu=index,utilization.gpu,power.draw,temperature.gpu,clocks.sm,clocks.mem --format=csv,noheader; echo; systemctl is-active llama-judge pcie-flight-recorder gpu-powerlimit | tr \"\\n\" \" \"; echo; wc -l \"\$(ls -t \"$MLECU/infrastructure/monitoring\"/pcie-flight-*.log | head -1)\"'" C-m

tmux attach -t "$S"
