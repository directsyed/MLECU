#!/usr/bin/env bash
# Set the NASIOC cf_clearance cookie and (optionally) run a pull.
#
# Usage:
#   bash nasioc-cookie.sh '<cf_clearance value>'        # just write the cookie
#   bash nasioc-cookie.sh '<cf_clearance value>' --pull # write it, then scrape now
#
# The cookie is bound to the browser User-Agent that solved the Cloudflare challenge, and it
# lives only HOURS — so export it fresh (same Chrome profile) right before you intend to pull.
# UA is pinned in config.yaml (pipeline.user_agent_pool); do not change one without the other.
set -euo pipefail

COOKIE="${1:-}"
DIR="$(cd "$(dirname "$0")" && pwd)"                     # this script's own directory
OUT="$DIR/data/raw/.cf-cookies/nasioc.json"

if [ -z "$COOKIE" ]; then
    echo "usage: bash nasioc-cookie.sh '<cf_clearance value>' [--pull]" >&2
    exit 1
fi
if [ "${#COOKIE}" -lt 40 ]; then                         # sanity: real tokens are long
    echo "refusing: that doesn't look like a cf_clearance value (too short)" >&2
    exit 1
fi

mkdir -p "$(dirname "$OUT")"
# Write the one-key JSON the loader expects. printf (not echo) so backslashes stay literal.
printf '{"cf_clearance": "%s"}\n' "$COOKIE" > "$OUT"
echo "wrote $OUT"

if [ "${2:-}" = "--pull" ]; then
    echo "running NASIOC pull (canary validates the cookie first)..."
    "$DIR/.venv/bin/python" -m corpus_pipeline.cli --once --sources forum_nasioc
fi
