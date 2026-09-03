#!/usr/bin/env bash
# PCIe flight recorder: 1 Hz samples of the slot-3 GPU + its root port, fsync'd per line so
# the final pre-crash samples SURVIVE a bus-fatal hang. Run with sudo in its own tmux window:
#
#   sudo bash infrastructure/monitoring/pcie-flight-recorder.sh
#
# Captures per second:
#   - nvidia-smi: pstate, link gen/width, temp, power, clocks, util, vram (both GPUs)
#   - PCIe Replay counter (NVIDIA's own count of link-level retries: rises on a bad link)
#   - lspci CESta/UESta raw error-status registers on the root port AND the GPU
#     (readable even when firmware-first AER hides errors from the kernel)
#   - kernel sysfs AER counters (zeros under firmware-first = itself a finding)
# One-time header: lspci tree, full root-port + GPU PCIE state.
set -u
# Auto-detect the OEM 3090's PCI address (survives slot moves: 2026-07-06 slot-1 test).
# The " Ti]" suffix keeps the match from hitting the 3090 Ti.
GPU_BDF=$(lspci -Dnn | grep -i "GeForce RTX 3090\]" | head -1 | awk '{print $1}')
[ -z "$GPU_BDF" ] && GPU_BDF="0000:04:00.0"   # fallback: last known address
PORT_BDF=$(basename "$(dirname "$(readlink "/sys/bus/pci/devices/$GPU_BDF")")")
STAMP=$(date +%Y%m%d-%H%M%S)
OUT="${1:-$(dirname "$0")/pcie-flight-$STAMP.log}"

log() { echo "$@" >> "$OUT"; sync "$OUT" 2>/dev/null || sync; }

log "=== FLIGHT RECORDER start $(date -Is) gpu=$GPU_BDF root_port=$PORT_BDF out=$OUT ==="
log "=== lspci -t ==="
lspci -t >> "$OUT"
log "=== one-time root port state ==="
lspci -s "${PORT_BDF#0000:}" -vv >> "$OUT" 2>&1
log "=== one-time GPU PCIE state ==="
nvidia-smi -q -i 0 -d PCIE >> "$OUT" 2>&1
log "=== sampling at 1 Hz, columns: time | nv(idx,pstate,gen,width,temp,W,sm,mem,util,vram) | replay | CESta/UESta rp,gpu | sysfs aer rp ==="

aer_sysfs() {  # $1 = bdf
  local d="/sys/bus/pci/devices/$1" out=""
  for f in aer_dev_correctable aer_dev_nonfatal aer_dev_fatal; do
    [ -r "$d/$f" ] && out+="$f{$(tr '\n' ' ' < "$d/$f" | sed 's/  */ /g')} "
  done
  echo "$out"
}

while true; do
  TS=$(date +%H:%M:%S)
  NV=$(nvidia-smi --query-gpu=index,pstate,pcie.link.gen.current,pcie.link.width.current,temperature.gpu,power.draw,clocks.sm,clocks.mem,utilization.gpu,memory.used --format=csv,noheader 2>&1 | tr '\n' ';')
  RPLY=$(nvidia-smi -q -d PCIE 2>/dev/null | grep -i "Replay" | sed 's/  *//g' | tr '\n' ' ')
  STA_RP=$(lspci -s "${PORT_BDF#0000:}" -vv 2>/dev/null | grep -E "CESta|UESta" | sed 's/^[ \t]*//' | tr '\n' '|')
  STA_GPU=$(lspci -s "${GPU_BDF#0000:}" -vv 2>/dev/null | grep -E "CESta|UESta" | sed 's/^[ \t]*//' | tr '\n' '|')
  log "$TS NV[$NV] $RPLY RP{$STA_RP} GPU{$STA_GPU} SYSFS[$(aer_sysfs "$PORT_BDF")]"
  sleep 1
done
