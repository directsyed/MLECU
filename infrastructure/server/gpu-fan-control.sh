#!/usr/bin/env bash
#
# gpu-fan-control.sh — closed-loop chassis-fan control for the T630 (MLECU)
#
# WHY THIS EXISTS
#   The iDRAC's automatic fan control is blind to the third-party RTX 3090 — in
#   auto mode it can't read the card, assumes worst-case, and slams the chassis
#   fans to 100% (jet engine). Manual mode quiets them but is STATIC: it won't
#   ramp when the GPU heats under load. This daemon closes that loop — poll GPU
#   (and CPU) temps, map them through a fan curve, and drive the chassis fans via
#   ipmitool. It re-asserts manual mode continuously so a BMC hiccup can't strand
#   the fans low.
#
# FAIL-SAFE PHILOSOPHY: every failure path ramps fans UP, never down. If we can't
#   read the GPU we assume it's hot. On exit we hand control back to iDRAC auto —
#   which (because of the GPU) means MAX fans: loud, but guaranteed cooling. That
#   is the correct dead-man's switch.
#
# Runs as root (ipmitool needs the local BMC/KCS interface). See the .service unit.
# Safe dry run:  ./gpu-fan-control.sh selftest   (prints the curve, touches nothing)

set -uo pipefail

# ----- Tunables -------------------------------------------------------------
INTERVAL=10      # seconds between polls
REFRESH=60       # re-assert the fan command at least this often, even if unchanged (BMC self-heal)
STEP=3           # only change fan % when the target moves at least this many points (anti-flap)
FLOOR=30         # minimum fan % — your proven-quiet idle; keeps minimum chassis airflow
FAILSAFE=80      # fan % forced when a sensor read fails (fans UP on the unknown)

# Curve anchors "tempC:pct", piecewise-linear between them; flat outside the ends.
GPU_CURVE=( "40:30" "70:70" "80:100" )   # GPU core (LOCKED 2026-06-22; revisit after the soak)
CPU_CURVE=( "50:30" "80:100" )           # CPU secondary (E5-2630 v3, Tjmax ~86C); GPU usually dominates
# ----------------------------------------------------------------------------

log() { printf '%s  %s\n' "$(date '+%F %T')" "$*"; }

# Linear-interpolate temp through a curve of "tempC:pct" anchors (integer math).
curve_pct() {
  local temp="$1"; shift
  local -a pts=( "$@" ); local n=${#pts[@]}
  local t0 p0 t1 p1 i
  IFS=: read -r t0 p0 <<<"${pts[0]}";    (( temp <= t0 )) && { echo "$p0"; return; }
  IFS=: read -r t1 p1 <<<"${pts[n-1]}";  (( temp >= t1 )) && { echo "$p1"; return; }
  for (( i=1; i<n; i++ )); do
    IFS=: read -r t1 p1 <<<"${pts[i]}"
    if (( temp <= t1 )); then
      IFS=: read -r t0 p0 <<<"${pts[i-1]}"
      echo $(( p0 + (temp - t0) * (p1 - p0) / (t1 - t0) )); return
    fi
  done
  echo "$p1"
}

read_gpu_temp() {
  local t
  t=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null | head -n1 | tr -dc '0-9')
  [[ -n "$t" ]] && echo "$t" || return 1
}

read_cpu_temp() {
  # iDRAC CPU temp = the "Temp" sensor (0Eh, entity 3.1). Take the first "ok" Temp line.
  local t
  t=$(ipmitool sdr type temperature 2>/dev/null | awk -F'|' '/^Temp/ && /ok/ {gsub(/[^0-9]/,"",$5); print $5; exit}')
  [[ -n "$t" ]] && echo "$t" || return 1
}

# ----- selftest: prove the curve math, no hardware, no root -----------------
if [[ "${1:-}" == "selftest" ]]; then
  printf 'tempC  gpu%%  cpu%%  applied(max, floor=%s)\n' "$FLOOR"
  for t in 30 35 40 45 50 55 60 65 70 75 80 85 90; do
    g=$(curve_pct "$t" "${GPU_CURVE[@]}"); c=$(curve_pct "$t" "${CPU_CURVE[@]}")
    m=$(( g > c ? g : c )); (( m < FLOOR )) && m=$FLOOR; (( m > 100 )) && m=100
    printf '%4d   %3d   %3d   %3d\n' "$t" "$g" "$c" "$m"
  done
  exit 0
fi

# ----- live control ---------------------------------------------------------
apply_fan() {
  local pct="$1" hex
  printf -v hex '0x%02x' "$pct"
  ipmitool raw 0x30 0x30 0x01 0x00 >/dev/null 2>&1        # keep manual mode on (self-heals a BMC revert)
  ipmitool raw 0x30 0x30 0x02 0xff "$hex" >/dev/null 2>&1 # set ALL fans to pct
}

cleanup() {
  log "exit -> handing fans back to iDRAC auto (dead-man's switch; fans will max)"
  ipmitool raw 0x30 0x30 0x01 0x01 >/dev/null 2>&1
  exit 0
}
trap cleanup SIGINT SIGTERM

[[ $EUID -eq 0 ]] || { log "FATAL: must run as root (ipmitool needs the local BMC)"; exit 1; }
ipmitool raw 0x30 0x30 0x01 0x00 >/dev/null 2>&1 || { log "FATAL: ipmitool failed (ipmi modules loaded?)"; exit 1; }
log "gpu-fan-control started (floor=${FLOOR}% interval=${INTERVAL}s)"

last_pct=-1; last_apply=0
while true; do
  now=$SECONDS
  if gpu_t=$(read_gpu_temp); then gpu_pct=$(curve_pct "$gpu_t" "${GPU_CURVE[@]}")
  else gpu_t="ERR"; gpu_pct=$FAILSAFE; log "WARN: GPU read failed -> failsafe ${FAILSAFE}%"; fi
  if cpu_t=$(read_cpu_temp); then cpu_pct=$(curve_pct "$cpu_t" "${CPU_CURVE[@]}")
  else cpu_t="ERR"; cpu_pct=$FLOOR; log "WARN: CPU read failed -> CPU term = floor"; fi

  target=$(( gpu_pct > cpu_pct ? gpu_pct : cpu_pct ))
  (( target < FLOOR )) && target=$FLOOR
  (( target > 100 )) && target=100

  if (( last_pct < 0 )) \
     || (( target >= 100 && last_pct < 100 )) \
     || (( target > last_pct + STEP || target < last_pct - STEP )) \
     || (( now - last_apply >= REFRESH )); then
    apply_fan "$target"
    log "gpu=${gpu_t}C(${gpu_pct}%) cpu=${cpu_t}C(${cpu_pct}%) -> fans ${target}%"
    last_pct=$target; last_apply=$now
  fi
  sleep "$INTERVAL"
done
