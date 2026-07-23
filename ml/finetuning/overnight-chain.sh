#!/usr/bin/env bash
# MLECU overnight chain — 2026-07-22 (Syed asleep; plan: ~/.claude/plans/snug-shimmying-spring.md)
# Train arm-C QLoRA -> serve adapter -> batteries C, D@6 -> base server -> B-v2@6 ->
# top_k sweeps (runs=1) -> judge batch (333 pending) -> done.
# Every stage logs here; a failed stage aborts its DEPENDENTS only. No sudo anywhere.

M="/home/syed/Shared/Computing Projects/MLECU"
V="$M/car/.venv/bin"
LOG="$M/ml/finetuning/logs/overnight-20260722.log"
SRVLOG="$M/ml/finetuning/logs/server-20260722.log"
LLS="/home/syed/tools/llama.cpp/build/bin/llama-server"
BASE_GGUF="$M/ml/curation/data/models/Qwen3.6-27B-Q8_0.gguf"
BF16_DIR="$M/ml/finetuning/models/Qwen3.6-27B"
ADAPTER_DIR="$M/ml/finetuning/runs/qlora-v1/adapter"
ADAPTER_GGUF="$M/ml/finetuning/runs/qlora-v1/adapter.gguf"
INDEX="$M/ml/eval/data/ref_dense_v1.npz"
FT_NAME="qwen3.6-27b-q8+qlora-v1"
BASE_NAME="qwen3.6-27b-q8_0"
SRV=""

log(){ echo "[$(date '+%F %T')] $*" >> "$LOG"; }

server_start(){                       # server_start <logtag> [extra llama-server flags...]
  local tag=$1; shift
  nohup "$LLS" -m "$BASE_GGUF" -ngl 999 --split-mode layer --tensor-split 3.5,1 \
    -c 16384 -np 1 --host 127.0.0.1 --port 8080 --jinja "$@" >> "$SRVLOG" 2>&1 &
  SRV=$!
  log "server[$tag] starting (pid $SRV) flags: $*"
  for _ in $(seq 1 90); do
    sleep 10
    curl -sf http://127.0.0.1:8080/v1/models >/dev/null 2>&1 && { log "server[$tag] healthy"; return 0; }
    kill -0 "$SRV" 2>/dev/null || { log "server[$tag] DIED during load"; return 1; }
  done
  log "server[$tag] health TIMEOUT"; kill "$SRV" 2>/dev/null; return 1
}

server_stop(){
  [ -n "$SRV" ] && kill "$SRV" 2>/dev/null
  sleep 8; pkill -f "llama-server .*--port 8080" 2>/dev/null; sleep 4
  log "server stopped"
}

battery(){                            # battery <arm> <e1_topk> <e2_topk> <runs> <model_name>
  local ARM=$1 K1=$2 K2=$3 RUNS=$4 NAME=$5
  log "battery arm=$ARM E1@$K1 E2@$K2 runs=$RUNS model=$NAME — order E1v2, E2, E1v1"
  cd "$M/ml/eval" || return 1
  "$V/python" -m harness.cli --run-e1 --arm "$ARM" --runs "$RUNS" \
      --cases data/sim_cases_v2.jsonl --top-k "$K1" --model-name "$NAME" >> "$LOG" 2>&1 \
      || log "arm $ARM E1v2 FAILED"
  "$V/python" -m harness.cli --run-e2 --arm "$ARM" --runs "$RUNS" \
      --probes data/e2_probes_v1.jsonl --top-k "$K2" --model-name "$NAME" >> "$LOG" 2>&1 \
      || log "arm $ARM E2 FAILED"
  "$V/python" -m harness.cli --run-e1 --arm "$ARM" --runs "$RUNS" \
      --top-k "$K1" --model-name "$NAME" >> "$LOG" 2>&1 \
      || log "arm $ARM E1v1 FAILED"
}

log "=========== CHAIN START ==========="

# ---- STAGE 0: training (smoke gate, then the real run) — Ti ONLY ----
log "=== STAGE 0: QLoRA training ==="
cd "$M"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True   # 04:30 fix: defragment the tight fit
if CUDA_VISIBLE_DEVICES=0 "$V/python" ml/finetuning/train.py --smoke >> "$LOG" 2>&1; then
  log "smoke OK — full run starting"
  if CUDA_VISIBLE_DEVICES=0 "$V/python" ml/finetuning/train.py >> "$LOG" 2>&1; then
    log "training COMPLETE"
    TRAINED=1
  else
    log "training FAILED — C/D batteries aborted"; TRAINED=0
  fi
else
  log "SMOKE FAILED — training + C/D aborted"; TRAINED=0
fi

# ---- STAGE 1: adapter -> GGUF ----
if [ "$TRAINED" = 1 ]; then
  log "=== STAGE 1: convert adapter to GGUF ==="
  if "$V/python" /home/syed/tools/llama.cpp/convert_lora_to_gguf.py "$ADAPTER_DIR" \
        --base "$BF16_DIR" --outfile "$ADAPTER_GGUF" --outtype f16 >> "$LOG" 2>&1; then
    log "adapter GGUF ready: $(du -h "$ADAPTER_GGUF" | cut -f1)"
  else
    log "adapter conversion FAILED — C/D batteries aborted"; TRAINED=0
  fi
fi

# ---- STAGE 2+3: fine-tuned server -> C battery, D battery (primary, runs=2) ----
if [ "$TRAINED" = 1 ]; then
  log "=== STAGE 2: arm C battery (fine-tune, no retrieval) ==="
  if server_start ft --lora "$ADAPTER_GGUF"; then          # NO MTP with adapter (untested combo)
    battery C 6 6 2 "$FT_NAME"
    log "=== STAGE 3: arm D battery (fine-tune + hybrid retrieval @6) ==="
    for _ in $(seq 1 120); do [ -f "$INDEX" ] && break; sleep 30; done
    if [ -f "$INDEX" ]; then
      battery D 6 6 2 "$FT_NAME"
      log "=== STAGE 6a: arm D top_k sweeps (runs=1, determinism proven 588/588x2) ==="
      battery D 3 6 1 "$FT_NAME|e1k3-e2k6"
      battery D 3 3 1 "$FT_NAME|k3-all"
    else
      log "dense index NEVER appeared — D batteries ABORTED (no mislabeled cells)"
    fi
    server_stop
  else
    log "fine-tuned server failed — C/D skipped"
  fi
fi

# ---- STAGE 4: base server (certified judge config, MTP on) -> B-v2 battery + sweeps ----
log "=== STAGE 4: arm B-v2 battery (base + hybrid retrieval @6) ==="
# 04:30 fix: HARD index requirement — first chain ran B-v2 on silent BM25 fallback
# (mislabeled cell, quarantined in results/aborted-20260723). Retrieval batteries now
# refuse to start hybrid-labeled without the dense index.
for _ in $(seq 1 240); do [ -f "$INDEX" ] && break; sleep 30; done
if [ ! -f "$INDEX" ]; then
  log "dense index NEVER appeared — B-v2 battery ABORTED (no mislabeled cells)"
elif server_start base --spec-type draft-mtp; then
  battery B 6 6 2 "$BASE_NAME"
  log "=== STAGE 6b: arm B-v2 top_k sweeps (runs=1) ==="
  battery B 3 6 1 "$BASE_NAME|e1k3-e2k6"
  battery B 3 3 1 "$BASE_NAME|k3-all"

  # ---- STAGE 5: judge batch on the SAME base server (its certified config) ----
  log "=== STAGE 5: judge batch — 333 pending docs incl. re-queued 5781 ==="
  cd "$M/ml/curation" || true
  "$V/python" -m judge.cli --run >> "$LOG" 2>&1 || log "judge batch FAILED (non-fatal)"
  server_stop
else
  log "base server failed — B-v2 + judge batch skipped"
fi

log "=========== CHAIN COMPLETE ==========="
