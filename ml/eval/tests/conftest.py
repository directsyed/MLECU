"""Put the car package on sys.path so the E4 tests can exercise the real deterministic layer.

E4 is the only suite that spans both trees: the eval harness lives in ml/eval and the tuning
algorithms + safety clamps live in car/ecutune. Testing E4 against a MOCK of the clamp layer
would defeat the point, the property under test is that the language model cannot reach a
table value, and that property lives in the real code. car/.venv already carries everything
both trees need (verified 2026-08-01), so the only missing piece is the import path.
"""
from __future__ import annotations

import sys
from pathlib import Path

CAR = Path(__file__).resolve().parents[3] / "car"
if CAR.exists() and str(CAR) not in sys.path:
    sys.path.insert(0, str(CAR))
