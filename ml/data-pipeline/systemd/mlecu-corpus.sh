#!/usr/bin/env bash
# One corpus-ingestion pass, for the systemd oneshot. Installed to ~/.local/bin/ (no spaces)
# so the unit's ExecStart avoids escaping the "Computing Projects" path.
set -uo pipefail
cd "/home/syed/Shared/Computing Projects/MLECU/ml/data-pipeline" || exit 1
export PYTHONPATH="$PWD"
exec ./.venv/bin/python -m corpus_pipeline.cli --once
