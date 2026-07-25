#!/usr/bin/env bash
# B-v3 gate re-run + repaired judge batch (plan of record 2026-07-25 §1).
M="/home/syed/Shared/Computing Projects/MLECU"
V="$M/car/.venv/bin"
LOG="$M/ml/finetuning/logs/bv3-20260725.log"
LLS="/home/syed/tools/llama.cpp/build/bin/llama-server"
BASE_GGUF="$M/ml/curation/data/models/Qwen3.6-27B-Q8_0.gguf"
log(){ echo "[$(date '+%F %T')] $*" >> "$LOG"; }

log "=== B-v3 chain start ==="
nohup "$LLS" -m "$BASE_GGUF" -ngl 999 --split-mode layer --tensor-split 3.5,1 \
  -c 16384 -np 1 --spec-type draft-mtp --host 127.0.0.1 --port 8080 --jinja \
  >> "$M/ml/finetuning/logs/server-bv3.log" 2>&1 &
SRV=$!
for _ in $(seq 1 60); do
  sleep 10
  curl -sf http://127.0.0.1:8080/v1/models >/dev/null 2>&1 && break
  kill -0 "$SRV" 2>/dev/null || { log "server died during load"; exit 1; }
done
curl -sf http://127.0.0.1:8080/v1/models >/dev/null 2>&1 || { log "server health timeout"; exit 1; }
log "base server healthy (pid $SRV, certified judge config, MTP on)"

cd "$M/ml/eval" || exit 1
log "=== B-v3 E2 battery: hybrid@6 + citation guard, 2 runs ==="
"$V/python" -m harness.cli --run-e2 --arm B --runs 2 --guard --top-k 6 \
    --probes data/e2_probes_v1.jsonl \
    --model-name "qwen3.6-27b-q8_0|hybrid-k6+guard-v1" >> "$LOG" 2>&1 \
    || log "B-v3 E2 FAILED"

log "=== judge batch (correct venv this time: ml/curation/.venv) ==="
cd "$M/ml/curation" || exit 1
".venv/bin/python" -m judge.cli --run >> "$LOG" 2>&1 || log "judge batch FAILED"

kill "$SRV" 2>/dev/null; sleep 5
log "=== B-v3 chain DONE ==="
